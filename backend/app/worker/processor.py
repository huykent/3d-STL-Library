"""arq worker task: full 3D model processing pipeline.

This function is called by arq when a 'process_telegram_message' job is
dequeued from Redis. It orchestrates the full pipeline:

  1. Look up Model3D in DB by telegram_message_id
  2. Download temp STL/OBJ from Telegram
  3. Analyze geometry with trimesh (stl_analyzer)
  4. Render thumbnail with pyrender (thumbnail)
  5. Get AI tags from Ollama (ai_tagger)
  6. Persist all results to PostgreSQL
  7. Delete temp file — ALWAYS, even on failure (try/finally)

Critical constraint: temp file MUST be cleaned up in a try/finally block.
"""
from __future__ import annotations

import logging
import os
import time
import asyncio

from sqlalchemy import select


from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.model3d import DetailLevel, Model3D, PrintType, ProcessingStatus
from app.services.ai_tagger import tag_model
from app.services.stl_analyzer import analyze_mesh
from app.services.thumbnail import render_thumbnail
from app.telegram.downloader import download_telegram_document, extract_3d_files

logger = logging.getLogger(__name__)

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

async def _add_log(session: AsyncSession, model: Model3D, step: str, message: str, path: str = None) -> None:
    """Helper to append a processing log and commit immediately."""
    from datetime import datetime
    log_entry = {
        "step": step,
        "message": message,
        "time": datetime.utcnow().isoformat()
    }
    if path:
        log_entry["path"] = path
    
    current_logs = model.processing_logs or []
    current_logs.append(log_entry)
    model.processing_logs = list(current_logs)
    model.updated_at = datetime.utcnow()
    
    logger.info(f"[{model.id}] {step}: {message}")


async def _add_log_by_id(model_id, step: str, message: str) -> None:
    """Independent session helper for background thread logging during download."""
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Model3D).where(Model3D.id == model_id)
            res = await session.execute(stmt)
            m = res.scalars().first()
            if m:
                logs = list(m.processing_logs or [])
                logs.append({
                    "step": step,
                    "message": message,
                    "time": datetime.utcnow().isoformat()
                })
                m.processing_logs = logs
                m.updated_at = datetime.utcnow()
                await session.commit()
    except Exception as e:
        logger.warning(f"Error in _add_log_by_id: {e}")

    await session.commit()


async def _fetch_related_images(telegram_client, chat_id: int, base_message) -> list:
    """Fetch images that belong to the same album or are directly related to base_message."""
    from telethon.tl.types import MessageMediaPhoto
    
    images = []
    try:
        grouped_id = base_message.grouped_id
        
        # We need to fetch messages around the base_message (e.g. 10 messages before and after)
        messages = await telegram_client.get_messages(chat_id, limit=20, offset_id=base_message.id + 10)
        if not messages:
            return []
        
        for msg in messages:
            if msg.id == base_message.id:
                continue
                
            is_image = False
            if isinstance(msg.media, MessageMediaPhoto):
                is_image = True
            elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith('image/'):
                is_image = True
                
            if not is_image:
                continue
                
            if grouped_id:
                # Case 1: base_message belongs to a Telegram Media Group (Album)
                # ONLY photos sharing the exact same grouped_id belong to this model post.
                if msg.grouped_id == grouped_id:
                    images.append(msg)
            else:
                # Case 2: base_message does NOT have a grouped_id (standalone file)
                # a) Skip any photo that belongs to a media group (msg.grouped_id is not None)
                if msg.grouped_id is not None:
                    continue
                    
                # b) Check strict proximity (within 2 message IDs and 60 seconds) or direct reply
                id_diff = abs(msg.id - base_message.id)
                time_diff = abs((msg.date - base_message.date).total_seconds())
                
                is_reply = (
                    getattr(msg, 'reply_to_msg_id', None) == base_message.id or
                    getattr(base_message, 'reply_to_msg_id', None) == msg.id
                )
                
                if is_reply or (id_diff <= 2 and time_diff <= 60 and msg.sender_id == base_message.sender_id):
                    images.append(msg)
                    
        # Sort images by message ID ascending to preserve chronological order
        images.sort(key=lambda m: m.id)
                    
    except Exception as e:
        logger.error(f"Error fetching related images: {e}")
        
    return images


async def process_telegram_message(ctx: dict, message_id: int, chat_id: int) -> None:
    """arq task: download and process a Telegram 3D model message.

    Args:
        ctx: arq worker context dictionary. Must contain 'telegram_client'.
        message_id: Telegram message ID of the file message.
        chat_id: Telegram chat/group ID where the message was posted.
    """
    settings = get_settings()
    telegram_client = ctx.get("telegram_client")
    tmp_file: str | None = None

    async with AsyncSessionLocal() as session:
        if not telegram_client.is_connected():
            await telegram_client.connect()

        # ── Fetch Telegram message first to get filename ─────────────────
        tg_message = await telegram_client.get_messages(chat_id, ids=message_id)

        if not tg_message or not tg_message.document:
            logger.error(f"Cannot find valid telegram message {message_id} in {chat_id}")
            return
            
        file_name = "unknown_file"
        for attribute in tg_message.document.attributes:
            if hasattr(attribute, 'file_name'):
                file_name = attribute.file_name
                break

        # ── Find internal Source Group ID ─────────────────────────────────
        from app.models.source_group import SourceGroup
        stmt_sg = select(SourceGroup).where(SourceGroup.chat_id == chat_id)
        source_group = (await session.execute(stmt_sg)).scalar_one_or_none()
        internal_sg_id = source_group.id if source_group else None

        # ── Find existing Model3D record ──────────────────────────────────
        file_id_str = str(tg_message.document.id)
        file_size = tg_message.document.size
        stmt = select(Model3D).where(
            (Model3D.telegram_message_id == message_id) |
            (Model3D.telegram_file_id == file_id_str) |
            ((Model3D.original_filename == file_name) & (Model3D.file_size_bytes == file_size))
        )
        result = await session.execute(stmt)
        model = result.scalars().first()

        if model is None:
            logger.info(f"Creating new Model3D record for message_id={message_id}")
            model = Model3D(
                telegram_file_id=file_id_str,
                telegram_message_id=message_id,
                source_group_id=internal_sg_id,
                original_filename=file_name,
                file_extension=file_name.split('.')[-1].lower() if '.' in file_name else "",
                file_size_bytes=file_size,
                processing_status=ProcessingStatus.processing,
                processing_retries=1
            )
            session.add(model)
            await session.flush()
        else:
            if model.processing_status == ProcessingStatus.completed:
                logger.info(f"Model {model.id} ({file_name}) already completed. Skipping re-processing.")
                return
            model.processing_status = ProcessingStatus.processing
            model.processing_retries = (model.processing_retries or 0) + 1
            
        await session.commit()


        try:
            pipeline_start = time.time()

            # ── Step 1: Download temp file from Telegram (10% -> 30%) ───────
            tmp_dir = settings.TEMP_DIR
            os.makedirs(tmp_dir, exist_ok=True)

            await _add_log(session, model, "Tải file (10%)", f"[10%] Bắt đầu tải file '{model.original_filename}' từ Telegram...")

            dl_start = time.time()
            last_log_time = [0.0]
            current_loop = asyncio.get_event_loop()

            def dl_progress_callback(downloaded, total):
                now = time.time()
                if now - last_log_time[0] >= 2.0 or downloaded == total:
                    last_log_time[0] = now
                    elapsed = now - dl_start
                    pct = int(10 + (downloaded / total) * 20) if total else 10
                    dl_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    speed = (dl_mb / elapsed) if elapsed > 0 else 0
                    eta_sec = int((total - downloaded) / (speed * 1024 * 1024)) if speed > 0 else 0
                    log_msg = (
                        f"[{pct}%] Đang tải: {dl_mb:.1f}/{tot_mb:.1f} MB "
                        f"({int(downloaded/total*100) if total else 0}%) | Tốc độ: {speed:.1f} MB/s | Dự kiến còn lại: ~{eta_sec}s"
                    )
                    logger.info(f"[{model.original_filename}] {log_msg}")
                    try:
                        if current_loop and current_loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                _add_log_by_id(model.id, f"Tải file ({pct}%)", log_msg),
                                current_loop
                            )

                    except Exception:
                        pass

            tmp_file = await download_telegram_document(
                telegram_client, tg_message, save_dir=tmp_dir, progress_callback=dl_progress_callback
            )

            file_size_mb = (os.path.getsize(tmp_file) / (1024 * 1024)) if os.path.exists(tmp_file) else 0
            await _add_log(session, model, "Tải file (30%)", f"[30%] Tải thành công file '{model.original_filename}' ({file_size_mb:.1f} MB) trong {time.time()-dl_start:.1f}s", path=tmp_file)

            # ── Step 1.5: Extract archive if needed (40%) ─────────────────
            extract_dir = os.path.join(tmp_dir, f"ext_{model.id}")
            await _add_log(session, model, "Xả nén (40%)", f"[40%] Đang kiểm tra định dạng và xả nén file '{model.original_filename}'...")
            extracted_files = await extract_3d_files(tmp_file, extract_dir)
            
            if not extracted_files:
                raise ValueError("No .stl, .obj, .3mf, .pm7m or .pwscene files found in the archive.")
                
            model.part_count = len(extracted_files)
                
            # Process the first valid 3D file found
            target_3d_file = extracted_files[0]
            await _add_log(session, model, "Xả nén (45%)", f"[45%] Tìm thấy file 3D chính: {os.path.basename(target_3d_file)}", path=target_3d_file)

            # ── Step 2: Analyze mesh geometry (55%) ───────────────────────
            await _add_log(session, model, "Đo đạc 3D (55%)", f"[55%] Đang phân tích lưới 3D tam giác (Trimesh) của {os.path.basename(target_3d_file)}...")
            analysis = analyze_mesh(target_3d_file)
            await _add_log(session, model, "Đo đạc 3D (65%)", 
                f"[65%] Đo đạc 3D hoàn tất: {analysis.face_count:,} mặt | "
                f"Kích thước: {analysis.bbox_x_mm:.1f}×{analysis.bbox_y_mm:.1f}×{analysis.bbox_z_mm:.1f}mm"
            )

            # ── Step 3: Render thumbnail (75%) ─────────────────────────────
            await _add_log(session, model, "Thumbnail (75%)", f"[75%] Đang dựng hình 3D EGL offscreen & chụp Thumbnail...")
            thumb_filename = f"{model.id}.png"
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_filename)
            render_thumbnail(target_3d_file, thumb_path)
            model.thumbnail_path = thumb_filename
            await _add_log(session, model, "Thumbnail (80%)", f"[80%] Đã tạo ảnh Thumbnail 3D thành công", path=thumb_path)
            
            # ── Step 3.5: Fetch related Telegram Images (82%) ─────────────
            await _add_log(session, model, "Album (82%)", "[82%] Đang tìm kiếm các ảnh demo đính kèm trong bài viết...")
            related_image_messages = await _fetch_related_images(telegram_client, chat_id, tg_message)
            
            image_paths = []
            if related_image_messages:
                await _add_log(session, model, "Album (85%)", f"[85%] Tìm thấy {len(related_image_messages)} ảnh demo. Đang tải album...")
                for i, img_msg in enumerate(related_image_messages):
                    try:
                        ext = '.jpg'
                        if img_msg.document and img_msg.document.attributes:
                            for attr in img_msg.document.attributes:
                                if hasattr(attr, 'file_name') and '.' in attr.file_name:
                                    ext = '.' + attr.file_name.split('.')[-1]
                                    break
                                    
                        img_filename = f"{model.id}_{i+1}{ext}"
                        img_path = os.path.join(settings.THUMBNAIL_DIR, img_filename)
                        await telegram_client.download_media(img_msg, file=img_path)
                        if os.path.exists(img_path):
                            image_paths.append(img_filename)
                    except Exception as e:
                        logger.error(f"Failed to download related image: {e}")
                        
                await _add_log(session, model, "Album (88%)", f"[88%] Tải thành công {len(image_paths)} ảnh demo.")
                model.image_paths = image_paths
            else:
                await _add_log(session, model, "Album (88%)", "[88%] Bài viết không chứa album ảnh đính kèm.")

            # ── Step 4: Phân loại / AI Tagging (90%) ──────────────────────
            message_text = tg_message.text or ""
            if not message_text and related_image_messages:
                for img_msg in related_image_messages:
                    if getattr(img_msg, 'text', None):
                        message_text = img_msg.text
                        break

            import re
            hashtags = re.findall(r'#\w+', message_text)
            
            if len(hashtags) >= 2 and len(message_text.strip()) > 5:
                await _add_log(session, model, "Phân loại (90%)", f"[90%] Bài viết gốc có sẵn {len(hashtags)} hashtags, bỏ qua AI để tối ưu thời gian.")
                cleaned_text = re.sub(r'#\w+', '', message_text).strip()
                lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
                
                predicted_name = lines[0][:100] if lines else model.original_filename.split('.')[0]
                
                model.predicted_name = predicted_name
                model.ai_category = "Uncategorized"
                model.ai_print_type = PrintType.Unknown
                model.ai_keywords = ", ".join([h.replace('#', '') for h in hashtags])
                model.ai_raw_response = "Bypassed AI (Manual parsing)"
            else:
                await _add_log(session, model, "AI Tagger (90%)", "[90%] Gửi dữ liệu và mô tả cho AI Ollama đặt tên & gắn tag...")
                
                ai_result = await tag_model(
                    filename=model.original_filename,
                    face_count=analysis.face_count,
                    bbox=(analysis.bbox_x_mm, analysis.bbox_y_mm, analysis.bbox_z_mm),
                    message_text=message_text,
                )
                await _add_log(session, model, "AI Tagger (93%)", 
                    f"[93%] AI hoàn tất: '{ai_result.predicted_name}' | Loại: {ai_result.print_type}"
                )
                
                model.predicted_name = ai_result.predicted_name
                model.ai_category = ai_result.category
                try:
                    model.ai_print_type = PrintType(ai_result.print_type)
                except ValueError:
                    model.ai_print_type = PrintType.Unknown
                model.ai_keywords = ai_result.keywords
                model.ai_raw_response = ai_result.raw_response

            # ── Step 5: Persist results to DB (95%) ───────────────────────
            model.vertex_count = analysis.vertex_count
            model.face_count = analysis.face_count
            model.detail_level = DetailLevel(analysis.detail_level.value)
            model.bbox_x_mm = analysis.bbox_x_mm
            model.bbox_y_mm = analysis.bbox_y_mm
            model.bbox_z_mm = analysis.bbox_z_mm
            model.volume_mm3 = analysis.volume_mm3
            model.thumbnail_path = thumb_filename

            model.processing_status = ProcessingStatus.completed
            model.processing_error = None

            # ── Step 6: Upload to Target Group (98%) ───────────────────────
            from app.services.settings import SettingsService
            target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
            if not target_chat_str:
                target_chat_str = settings.TELEGRAM_TARGET_CHAT_ID
                
            if target_chat_str and tmp_file and os.path.exists(tmp_file):
                try:
                    target_chat_id = int(target_chat_str.strip())
                    caption = (
                        f"**{model.predicted_name or model.original_filename}**\n\n"
                        f"📁 **File:** `{model.original_filename}`\n"
                        f"📊 **Faces:** {model.face_count:,}\n"
                        f"📏 **Size:** {model.bbox_x_mm:.1f} × {model.bbox_y_mm:.1f} × {model.bbox_z_mm:.1f} mm\n"
                        f"🏷️ **Tags:** {model.ai_keywords}\n"
                    )
                    
                    image_files = []
                    if model.image_paths:
                        for p in model.image_paths:
                            full_p = os.path.join(settings.THUMBNAIL_DIR, p)
                            if os.path.exists(full_p):
                                image_files.append(full_p)
                                
                    if image_files:
                        await _add_log(session, model, "Backup (98%)", f"[98%] Đang upload album ({len(image_files)} ảnh) + file 3D sang nhóm đích ({target_chat_id})...")
                        
                        album_msgs = await telegram_client.send_file(
                            target_chat_id, 
                            image_files,
                            caption=caption
                        )
                        
                        reply_to_msg_id = album_msgs[0].id if isinstance(album_msgs, list) else album_msgs.id
                        from telethon.tl.types import DocumentAttributeFilename
                        doc_msg = await telegram_client.send_file(
                            target_chat_id, 
                            tmp_file,
                            reply_to=reply_to_msg_id,
                            attributes=[DocumentAttributeFilename(file_name=model.original_filename)]
                        )
                        if doc_msg and doc_msg.document:
                            model.telegram_file_id = str(doc_msg.document.id)
                    else:
                        await _add_log(session, model, "Backup (98%)", f"[98%] Đang upload file 3D kèm mô tả sang nhóm đích ({target_chat_id})...")
                        tg_msg = await telegram_client.send_file(
                            target_chat_id, 
                            tmp_file, 
                            thumb=thumb_path if os.path.exists(thumb_path) else None,
                            caption=caption
                        )
                        if tg_msg and tg_msg.document:
                            model.telegram_file_id = str(tg_msg.document.id)

                    await session.commit()
                    await _add_log(session, model, "Backup (99%)", "[99%] Upload thành công lên nhóm đích.")
                except Exception as upload_exc:
                    logger.error(f"[{model.id}] Failed to upload to target group: {upload_exc}")

            total_elapsed = time.time() - pipeline_start
            await _add_log(session, model, "Hoàn tất (100%)", f"[100%] Hoàn tất 100% xử lý model '{model.original_filename}' trong {total_elapsed:.1f} giây!")


        except Exception as exc:
            model.processing_status = ProcessingStatus.failed
            model.processing_error = str(exc)
            await _add_log(session, model, "Lỗi hệ thống", f"Tiến trình thất bại: {exc}")
            logger.error(f"[{model.id}] Pipeline error: {exc}", exc_info=True)
            try:
                await session.commit()
            except Exception as db_exc:
                logger.error(f"[{model.id}] DB commit after failure also failed: {db_exc}")

        finally:
            # ── ALWAYS delete temp files and extraction dirs ──────────────
            import shutil
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                    await _add_log(session, model, "Dọn dẹp", f"Đã xoá file tạm thời", path=tmp_file)
                except OSError as e:
                    logger.warning(f"[{model.id}] Could not delete temp file {tmp_file}: {e}")
            if 'extract_dir' in locals() and os.path.exists(extract_dir):
                try:
                    shutil.rmtree(extract_dir)
                    await _add_log(session, model, "Dọn dẹp", f"Đã dọn dẹp thư mục xả nén", path=extract_dir)
                except OSError as e:
                    logger.warning(f"[{model.id}] Could not delete extract dir {extract_dir}: {e}")

            # Run a sweep on TEMP_DIR to purge any orphaned leftover temp files
            _cleanup_orphaned_temp_files(settings.TEMP_DIR)


def _cleanup_orphaned_temp_files(temp_dir: str, max_age_seconds: int = 1800) -> None:
    """Sweep and remove any temporary files or directories older than max_age_seconds."""
    import time
    import shutil
    if not os.path.exists(temp_dir):
        return

    now = time.time()
    for item in os.listdir(temp_dir):
        item_path = os.path.join(temp_dir, item)
        try:
            mtime = os.path.getmtime(item_path)
            if now - mtime > max_age_seconds:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                else:
                    os.unlink(item_path)
                logger.info(f"Auto-cleaned old temp item: {item_path}")
        except Exception as e:
            logger.warning(f"Could not clean temp item {item_path}: {e}")



async def process_manual_upload(ctx: dict, model_id: str, filepath: str) -> None:
    """arq task: Process a manually uploaded 3D model."""
    settings = get_settings()
    telegram_client = ctx.get("telegram_client")
    
    async with AsyncSessionLocal() as session:
        stmt = select(Model3D).where(Model3D.id == model_id)
        model = (await session.execute(stmt)).scalar_one_or_none()
        
        if not model:
            logger.error(f"process_manual_upload: Model {model_id} not found in DB")
            # Cleanup temp file
            if os.path.exists(filepath):
                os.unlink(filepath)
            return

        model.processing_status = ProcessingStatus.processing
        model.processing_retries = (model.processing_retries or 0) + 1
        await session.commit()
        
        extract_dir = os.path.join(settings.TEMP_DIR, f"ext_{model.id}")
        
        try:
            # 1. Extract if needed
            await _add_log(session, model, "Xả nén", "Bắt đầu xả nén file thủ công...")
            extracted_files = await extract_3d_files(filepath, extract_dir)
            if not extracted_files:
                raise ValueError("No .stl, .obj, .3mf, .pm7m or .pwscene files found in the archive.")
                
            model.part_count = len(extracted_files)
            target_3d_file = extracted_files[0]
            await _add_log(session, model, "Xả nén", "Tìm thấy file 3D để phân tích", path=target_3d_file)
            
            # 2. Upload to Telegram to get telegram_message_id and file_id
            # Fetch TELEGRAM_TARGET_CHAT_ID from settings
            from app.services.settings import SettingsService
            target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
            if not target_chat_str:
                target_chat_str = os.environ.get("TELEGRAM_BACKUP_CHAT_ID")
                
            if target_chat_str:
                backup_chat_id = int(target_chat_str.strip())
            else:
                chats = settings.chat_ids
                if not chats:
                    raise ValueError("No Telegram Target Chat ID configured.")
                backup_chat_id = chats[0]
            
            await _add_log(session, model, "Lưu trữ", f"Đang upload file lên Telegram backup group {backup_chat_id}...")
            tg_message = await telegram_client.send_file(
                backup_chat_id, 
                filepath, 
                caption=f"Manual Upload: {model.original_filename}"
            )
            model.telegram_message_id = tg_message.id
            model.telegram_file_id = str(tg_message.document.id)
            await _add_log(session, model, "Lưu trữ", "Upload lên Telegram thành công")
            
            # 3. Analyze Mesh
            await _add_log(session, model, "Đo đạc 3D", "Đang đọc lưới tam giác (Mesh) của file 3D...")
            analysis = analyze_mesh(target_3d_file)
            await _add_log(session, model, "Đo đạc 3D", 
                f"Đo đạc hoàn tất. Số mặt (faces): {analysis.face_count:,}, "
                f"Kích thước: {analysis.bbox_x_mm:.1f}×{analysis.bbox_y_mm:.1f}×{analysis.bbox_z_mm:.1f}mm."
            )
            
            # 4. Render Thumbnail
            await _add_log(session, model, "Thumbnail", "Đang chụp ảnh Thumbnail...")
            thumb_filename = f"{model.id}.png"
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_filename)
            render_thumbnail(target_3d_file, thumb_path)
            await _add_log(session, model, "Thumbnail", "Tạo Thumbnail thành công", path=thumb_path)
            
            # 5. Tag with AI
            await _add_log(session, model, "AI Tagger", "Gửi dữ liệu cho AI phân tích...")
            ai_result = await tag_model(
                filename=model.original_filename,
                face_count=analysis.face_count,
                bbox=(analysis.bbox_x_mm, analysis.bbox_y_mm, analysis.bbox_z_mm),
                message_text=f"Manual Upload: {model.original_filename}",
            )
            await _add_log(session, model, "AI Tagger", 
                f"Phân tích AI hoàn tất. Tên dự đoán: {ai_result.predicted_name}, "
                f"Loại: {ai_result.print_type}"
            )
            
            # 6. Update DB
            model.vertex_count = analysis.vertex_count
            model.face_count = analysis.face_count
            model.detail_level = DetailLevel(analysis.detail_level.value)
            model.bbox_x_mm = analysis.bbox_x_mm
            model.bbox_y_mm = analysis.bbox_y_mm
            model.bbox_z_mm = analysis.bbox_z_mm
            model.volume_mm3 = analysis.volume_mm3
            model.thumbnail_path = thumb_filename
            model.predicted_name = ai_result.predicted_name
            model.ai_category = ai_result.category
            try:
                model.ai_print_type = PrintType(ai_result.print_type)
            except ValueError:
                model.ai_print_type = PrintType.Unknown
            model.ai_keywords = ai_result.keywords
            model.ai_raw_response = ai_result.raw_response

            model.processing_status = ProcessingStatus.completed
            model.processing_error = None
            
            await _add_log(session, model, "Hoàn tất", "Xử lý file thủ công thành công!")

        except Exception as exc:
            model.processing_status = ProcessingStatus.failed
            model.processing_error = str(exc)
            await _add_log(session, model, "Lỗi hệ thống", f"Tiến trình thất bại: {exc}")
            logger.error(f"[{model.id}] Manual pipeline error: {exc}", exc_info=True)
            try:
                await session.commit()
            except Exception:
                pass
        finally:
            import shutil
            if os.path.exists(filepath):
                try:
                    os.unlink(filepath)
                except OSError:
                    pass
            if os.path.exists(extract_dir):
                try:
                    shutil.rmtree(extract_dir)
                except OSError:
                    pass
