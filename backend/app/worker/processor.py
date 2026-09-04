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
from app.services.fast_mesh import FastMeshInfo, inspect_3d_file, parse_stl_header_bytes
from app.telegram.downloader import download_telegram_document, extract_3d_files

logger = logging.getLogger(__name__)

# ── Global download lock: chỉ tải 1 file Telegram tại một thời điểm ──────────
# Giúp ngăn FloodWait do gửi quá nhiều request song song đến Telegram
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(3)  # Premium: cho phép 3 file tải song song

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


def _extract_3mf_thumbnail(file_path: str, output_dir: str, model_id: str) -> str | None:
    """Extract embedded plate thumbnail from Bambu Studio / OrcaSlicer .3mf file."""
    import zipfile
    import shutil
    try:
        if not file_path or not os.path.exists(file_path):
            return None
        
        # Check if it's a 3mf directly
        if file_path.lower().endswith('.3mf'):
            with zipfile.ZipFile(file_path, 'r') as z:
                plate_candidates = [
                    n for n in z.namelist() 
                    if ('plate_' in n.lower() or 'thumbnail' in n.lower()) and n.lower().endswith(('.png', '.jpg', '.jpeg'))
                ]
                plate_candidates.sort(key=lambda x: (not x.endswith('plate_1.png'), len(x)))
                if plate_candidates:
                    chosen = plate_candidates[0]
                    ext = os.path.splitext(chosen)[1]
                    out_filename = f"{model_id}_plate_1{ext}"
                    out_path = os.path.join(output_dir, out_filename)
                    with z.open(chosen) as src, open(out_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    logger.info(f"[{model_id}] Trích xuất thành công thumbnail 3MF gốc: {out_filename} ({chosen})")
                    return out_filename
        
        # If it's a .zip archive, check if there's an internal .3mf
        elif file_path.lower().endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as z:
                for name in z.namelist():
                    if name.lower().endswith('.3mf'):
                        import io
                        with z.open(name) as sub_3mf_file:
                            sub_bytes = io.BytesIO(sub_3mf_file.read())
                            with zipfile.ZipFile(sub_bytes, 'r') as sub_z:
                                plate_candidates = [
                                    n for n in sub_z.namelist() 
                                    if ('plate_' in n.lower() or 'thumbnail' in n.lower()) and n.lower().endswith(('.png', '.jpg', '.jpeg'))
                                ]
                                plate_candidates.sort(key=lambda x: (not x.endswith('plate_1.png'), len(x)))
                                if plate_candidates:
                                    chosen = plate_candidates[0]
                                    ext = os.path.splitext(chosen)[1]
                                    out_filename = f"{model_id}_plate_1{ext}"
                                    out_path = os.path.join(output_dir, out_filename)
                                    with sub_z.open(chosen) as src, open(out_path, 'wb') as dst:
                                        shutil.copyfileobj(src, dst)
                                    logger.info(f"[{model_id}] Trích xuất thành công thumbnail 3MF từ gói zip: {out_filename}")
                                    return out_filename
    except Exception as e:
        logger.debug(f"[{model_id}] Không thể trích xuất thumbnail 3MF: {e}")
    return None


async def _assign_tags_to_model(session: AsyncSession, model: Model3D, keyword_str: str) -> None:
    """Parse keyword string, upsert Tag records (PostgreSQL ON CONFLICT), and assign to model.tags."""
    import re as _re
    from app.models.tag import Tag
    from sqlalchemy import select as _select

    if not keyword_str:
        return

    # Clean tag names: remove emojis and special symbols so name and slug are clean
    raw_list = [k.strip().lower() for k in str(keyword_str).replace(',', ' ').split() if k.strip()]
    cleaned_names = []
    for k in raw_list:
        clean_w = _re.sub(r'[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF-]', '', k).strip()
        if clean_w and len(clean_w) >= 2:
            cleaned_names.append(clean_w)

    # De-duplicate while preserving order
    seen: set = set()
    tag_names = [n for n in cleaned_names if not (n in seen or seen.add(n))]  # type: ignore[func-returns-value]

    if not tag_names:
        return

    # Safe upsert tag using begin_nested() savepoint to prevent transaction rollback
    for name in tag_names:
        slug = _re.sub(r'[^a-z0-9]+', '-', name).strip('-')
        if not slug:
            slug = name.lower()
        try:
            async with session.begin_nested():
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(Tag).values(name=name, slug=slug).on_conflict_do_nothing(index_elements=['name'])
                await session.execute(stmt)
        except Exception as e:
            logger.warning(f"Could not upsert tag '{name}' (slug '{slug}'): {e}")

    # Re-query all valid tags
    existing_q = await session.execute(_select(Tag).where(Tag.name.in_(tag_names)))
    assigned = list(existing_q.scalars().all())

    # Async refresh tags relationship before assigning to avoid MissingGreenlet
    try:
        await session.refresh(model, ["tags"])
    except Exception:
        pass
    model.tags = assigned


async def _fetch_related_images(telegram_client, chat_id: int, base_message) -> list:
    """
    Fetch images that belong to the same album or are directly related to base_message.

    Covers 3 patterns:
      A) File + photos share the same grouped_id (Telegram Media Group / Album)
      B) Photos posted right before/after the file as a separate album (3D Pixel STL style with 4 demo photos)
      C) Photos posted as standalone messages adjacent to the file (no grouped_id)
    """
    from telethon.tl.types import MessageMediaPhoto

    images: list = []
    try:
        grouped_id = getattr(base_message, 'grouped_id', None)

        # ── Fetch messages BEFORE the base message (up to 12 messages older) ──
        msgs_before = await telegram_client.get_messages(
            chat_id, limit=12, offset_id=base_message.id
        )
        # ── Fetch messages AFTER the base message (min_id trick) ────────────
        msgs_after = await telegram_client.get_messages(
            chat_id, limit=12, min_id=base_message.id
        )

        all_msgs = list(msgs_before or []) + list(msgs_after or [])
        if not all_msgs:
            return []

        image_candidates = []
        for msg in all_msgs:
            if msg.id == base_message.id:
                continue

            # Check if message is a photo or image document
            is_image = False
            if isinstance(msg.media, MessageMediaPhoto):
                is_image = True
            elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith('image/'):
                is_image = True

            if is_image:
                image_candidates.append(msg)

        if not image_candidates:
            return []

        if grouped_id:
            # Pattern A: base_message belongs to an album
            images = [m for m in image_candidates if getattr(m, 'grouped_id', None) == grouped_id]
        else:
            # Pattern B + C: base_message is a file without grouped_id
            # 3D Pixel STL: 4 photos sent as an album right before or after the 3D file.
            
            # 1. Look for nearest photo album (grouped_id) adjacent to base_message
            grouped_candidates = {}
            for m in image_candidates:
                gid = getattr(m, 'grouped_id', None)
                if gid:
                    grouped_candidates.setdefault(gid, []).append(m)

            # Find if there is an album within 8 message IDs and 5 minutes
            best_album_id = None
            min_dist = 999
            for gid, plist in grouped_candidates.items():
                for m in plist:
                    id_dist = abs(m.id - base_message.id)
                    time_dist = abs((m.date - base_message.date).total_seconds()) if m.date and base_message.date else 0
                    if id_dist <= 8 and time_dist <= 300 and id_dist < min_dist:
                        min_dist = id_dist
                        best_album_id = gid

            if best_album_id and best_album_id in grouped_candidates:
                images = grouped_candidates[best_album_id]
            else:
                # Standalone photos: take up to 4 closest adjacent photos within 5 message IDs and 5 minutes
                standalone = []
                for m in image_candidates:
                    id_dist = abs(m.id - base_message.id)
                    time_dist = abs((m.date - base_message.date).total_seconds()) if m.date and base_message.date else 0
                    is_reply = (
                        getattr(m, 'reply_to_msg_id', None) == base_message.id or
                        getattr(base_message, 'reply_to_msg_id', None) == m.id
                    )
                    if is_reply or (id_dist <= 5 and time_dist <= 300):
                        standalone.append((id_dist, m))
                
                standalone.sort(key=lambda x: x[0])
                images = [item[1] for item in standalone[:4]]

        # Sort images in chronological order
        images.sort(key=lambda m: m.id)

    except Exception as e:
        logger.error(f"Error fetching related images: {e}")

    return images


async def process_telegram_message(ctx: dict, message_id: int, chat_id: int, **kwargs) -> None:
    """arq task: download and process a Telegram 3D model message.

    Args:
        ctx: arq worker context dictionary. Must contain 'telegram_client'.
        message_id: Telegram message ID of the file message.
        chat_id: Telegram chat/group ID where the message was posted.
    """
    settings = get_settings()
    telegram_client = ctx.get("telegram_client")
    tmp_file: str | None = None
    tmp_dir: str | None = None

    async with AsyncSessionLocal() as session:
        if not telegram_client.is_connected():
            await telegram_client.connect()

        # ── Fetch Telegram message first to get filename ─────────────────
        try:
            tg_message = await telegram_client.get_messages(chat_id, ids=message_id)
        except ValueError as ve:
            logger.warning(f"Cannot fetch message {message_id} from {chat_id}: {ve}")
            return

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
                telegram_file_id=None,  # Null cho tới khi upload thành công sang nhóm đích
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
            # Nếu model đã completed VÀ đã được upload lên nhóm đích (telegram_file_id is not None) -> Bỏ qua
            # Nếu model đã completed nhưng CHƯA upload lên nhóm đích (telegram_file_id is None) -> Chạy tiếp để upload
            from app.services.settings import SettingsService
            target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
            if not target_chat_str:
                target_chat_str = settings.TELEGRAM_TARGET_CHAT_ID

            already_uploaded = (model.telegram_file_id is not None)
            if model.processing_status == ProcessingStatus.completed and already_uploaded:
                logger.info(f"Model {model.id} ({file_name}) already completed and uploaded to target group. Skipping.")
                return
            
            model.processing_status = ProcessingStatus.processing
            model.processing_retries = (model.processing_retries or 0) + 1
            
        await session.commit()

        # ── Step 0: Fast-Forward Relay sang nhóm đích NGAY LẬP TỨC (0.05s) ──
        # Tác vụ forward KHÔNG TỐN BĂNG THÔNG, chạy ngay TRƯỚC DOWNLOAD_SEMAPHORE.
        # Giúp tất cả file trong hàng đợi được sao lưu và lấy File ID ngay lập tức
        # trong khi các file nặng khác đang tải xuống!
        from app.services.settings import SettingsService
        target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
        if not target_chat_str:
            target_chat_str = settings.TELEGRAM_TARGET_CHAT_ID

        target_entity = None
        if target_chat_str:
            try:
                target_chat_id = int(target_chat_str.strip())
                try:
                    target_entity = await telegram_client.get_entity(target_chat_id)
                except Exception:
                    await telegram_client.get_dialogs(limit=100)
                    target_entity = await telegram_client.get_entity(target_chat_id)

                if target_entity and not model.telegram_file_id:
                    try:
                        # Tìm ảnh đính kèm (Qua reply_to tin nhắn ảnh hoặc tin nhắn ảnh sát trước đó)
                        photo_ids = []
                        try:
                            msg_obj = await telegram_client.get_messages(chat_id, ids=message_id)
                            if msg_obj and msg_obj.reply_to and msg_obj.reply_to.reply_to_msg_id:
                                parent_msg = await telegram_client.get_messages(chat_id, ids=msg_obj.reply_to.reply_to_msg_id)
                                if parent_msg and parent_msg.photo:
                                    photo_ids.append(parent_msg.id)

                            if not photo_ids:
                                pre_msgs = await telegram_client.get_messages(
                                    chat_id, 
                                    ids=list(range(max(1, message_id - 4), message_id))
                                )
                                valid_pre = [m for m in pre_msgs if m is not None]
                                for pm in reversed(valid_pre):
                                    if pm.photo:
                                        photo_ids.insert(0, pm.id)
                                    elif pm.document:
                                        break
                        except Exception as pe:
                            logger.warning(f"Error finding companion photo for #{message_id}: {pe}")

                        all_ids = photo_ids + [message_id]
                        fwd_res = await telegram_client.forward_messages(
                            target_entity,
                            all_ids,
                            from_peer=chat_id
                        )
                        if fwd_res:
                            forwarded_doc = None
                            if isinstance(fwd_res, list):
                                for fm in reversed(fwd_res):
                                    if fm.document:
                                        forwarded_doc = fm
                                        break
                                if not forwarded_doc:
                                    forwarded_doc = fwd_res[-1]
                            else:
                                forwarded_doc = fwd_res

                            model.telegram_target_message_id = forwarded_doc.id
                            if forwarded_doc.document:
                                model.telegram_file_id = str(forwarded_doc.document.id)

                            # Tải nhanh ảnh thumbnail cho Web Dashboard
                            if photo_ids and not model.image_paths:
                                try:
                                    os.makedirs(settings.THUMBNAIL_DIR, exist_ok=True)
                                    th_name = f"{model.id}_preview.jpg"
                                    th_full = os.path.join(settings.THUMBNAIL_DIR, th_name)
                                    await telegram_client.download_media(photo_ids[0], file=th_full)
                                    if os.path.exists(th_full) and os.path.getsize(th_full) > 0:
                                        model.image_paths = [th_name]
                                except Exception as th_err:
                                    pass

                            await session.commit()
                            logger.info(f"[{model.id}] ⚡ ĐÃ FORWARD TỨC THÌ ({len(photo_ids)} ảnh + File) sang nhóm đích: Msg #{forwarded_doc.id} (File ID: {model.telegram_file_id})")
                            await _add_log(session, model, "Forward tức thì (5%)", f"[5%] Đã forward file kèm {len(photo_ids)} ảnh preview sang nhóm đích thành công!")
                    except Exception as fwd_err:
                        logger.info(f"[{model.id}] Kênh nguồn chặn forward ({fwd_err}). Sẽ tải về và upload ở bước sau.")
            except Exception as te_err:
                logger.warning(f"Target entity error in early forward: {te_err}")

        try:
            pipeline_start = time.time()

            # ── Step 1: Download temp file from Telegram (10% -> 30%) ───────
            tmp_dir = os.path.join(settings.TEMP_DIR, str(model.id))
            os.makedirs(tmp_dir, exist_ok=True)
            # Run immediate cleanup of any leftover temp files older than 2 minutes
            _cleanup_orphaned_temp_files(settings.TEMP_DIR, max_age_seconds=120)

            await _add_log(session, model, "Tải file (10%)", f"[10%] Bắt đầu tải file '{model.original_filename}' từ Telegram...")


            dl_start = time.time()
            last_log_time = [time.time()]
            last_downloaded = [0]
            current_loop = asyncio.get_event_loop()

            def dl_progress_callback(downloaded, total):
                now = time.time()
                time_diff = now - last_log_time[0]
                if time_diff >= 1.5 or downloaded == total:
                    bytes_diff = downloaded - last_downloaded[0]
                    # Instantaneous rolling speed (over last 1.5s window)
                    inst_speed_mb = (bytes_diff / (1024 * 1024)) / time_diff if time_diff > 0 else 0
                    last_log_time[0] = now
                    last_downloaded[0] = downloaded

                    pct = int(10 + (downloaded / total) * 20) if total else 10
                    dl_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    
                    remaining_bytes = max(0, total - downloaded)
                    eta_sec = int(remaining_bytes / (inst_speed_mb * 1024 * 1024)) if inst_speed_mb > 0.1 else 0
                    log_msg = (
                        f"[{pct}%] Đang tải: {dl_mb:.1f}/{tot_mb:.1f} MB "
                        f"({int(downloaded/total*100) if total else 0}%) | Tốc độ: {inst_speed_mb:.1f} MB/s | Dự kiến còn lại: ~{eta_sec}s"
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

            async def _flood_wait_status_callback(msg: str):
                """Forward FloodWait notices to the model's processing_logs."""
                await _add_log_by_id(model.id, "[Tạm dừng]", msg)

            async with DOWNLOAD_SEMAPHORE:
                tmp_file = await download_telegram_document(
                    telegram_client, tg_message, save_dir=tmp_dir,
                    progress_callback=dl_progress_callback,
                    status_callback=_flood_wait_status_callback
                )
                # Giãn cách nhỏ sau tải xong (Premium: giảm xuống 0.5s)
                await asyncio.sleep(0.5)

            file_size_mb = (os.path.getsize(tmp_file) / (1024 * 1024)) if os.path.exists(tmp_file) else 0
            await _add_log(session, model, "Tải file (30%)", f"[30%] Tải thành công file '{model.original_filename}' ({file_size_mb:.1f} MB) trong {time.time()-dl_start:.1f}s", path=tmp_file)

            # ── Step 1.5 & 2: Fast 3D / Archive Inspection (45%) ──────────
            await _add_log(session, model, "Phân tích nhanh (45%)", f"[45%] Đang quét cấu trúc file '{model.original_filename}'...")
            mesh_info = inspect_3d_file(tmp_file)
            model.part_count = mesh_info.part_count
            model.is_presupported = mesh_info.is_presupported
            model.face_count = mesh_info.face_count
            
            face_display = f"{mesh_info.face_count:,} mặt" if mesh_info.face_count else f"{mesh_info.part_count} part(s)"
            support_status_str = " (Có Pre-support)" if mesh_info.is_presupported else ""
            await _add_log(session, model, "Phân tích nhanh (55%)", f"[55%] Quét nhanh hoàn tất: {face_display}{support_status_str}")

            # ── Step 3: Fetch Telegram demo images (75%) ──────────────────
            await _add_log(session, model, "Album (75%)", "[75%] Đang tìm kiếm ảnh demo đính kèm trong bài viết Telegram...")
            related_image_messages = await _fetch_related_images(telegram_client, chat_id, tg_message)

            image_paths = []
            if related_image_messages:
                await _add_log(session, model, "Album (78%)", f"[78%] Tìm thấy {len(related_image_messages)} ảnh demo. Đang tải album...")
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

                model.image_paths = image_paths
                if image_paths:
                    model.thumbnail_path = image_paths[0]
                await _add_log(session, model, "Album (82%)", f"[82%] Tải thành công {len(image_paths)} ảnh demo từ Telegram.")
            else:
                await _add_log(session, model, "Album (78%)", "[78%] Không có ảnh demo đính kèm từ Telegram.")

            # Nếu chưa có ảnh demo, thử trích xuất trực tiếp từ file 3MF
            if not image_paths:
                extracted_thumb = _extract_3mf_thumbnail(tmp_file, settings.THUMBNAIL_DIR, str(model.id))
                if extracted_thumb:
                    image_paths.append(extracted_thumb)
                    model.thumbnail_path = extracted_thumb
                    model.image_paths = [extracted_thumb]
                    await _add_log(session, model, "Album (82%)", f"[82%] Đã trích xuất ảnh xem trước 3MF gốc chất lượng cao.")

            # ── Step 4: Phân loại / AI Tagging (90%) ──────────────────────
            message_text = tg_message.text or ""
            if not message_text and related_image_messages:
                for img_msg in related_image_messages:
                    if getattr(img_msg, 'text', None):
                        message_text = img_msg.text
                        break

            await _add_log(session, model, "AI Tagger (90%)", "[90%] Gửi dữ liệu cho AI Ollama nhận diện Studio, tên & phân loại...")
            ai_result = await tag_model(
                filename=model.original_filename,
                face_count=mesh_info.face_count,
                message_text=message_text,
                is_presupported=mesh_info.is_presupported,
            )
            
            model.predicted_name = ai_result.predicted_name
            model.studio_name = ai_result.studio
            model.ai_category = ai_result.category
            try:
                model.ai_print_type = PrintType(ai_result.print_type)
            except ValueError:
                model.ai_print_type = PrintType.Unknown
            model.ai_keywords = ai_result.keywords
            model.ai_raw_response = ai_result.raw_response

            studio_log_str = f" | Studio: {ai_result.studio}" if ai_result.studio else ""
            await _add_log(session, model, "AI Tagger (93%)", f"[93%] AI hoàn tất: '{ai_result.predicted_name}'{studio_log_str}")

            # ── Inject tên nhóm nguồn vào keywords ───────────────────────
            group_tag_name: str | None = None
            if source_group:
                group_tag_name = source_group.name
            elif internal_sg_id:
                from app.models.source_group import SourceGroup as _SG
                sg_r = await session.execute(select(_SG).where(_SG.id == internal_sg_id))
                sg_obj = sg_r.scalar_one_or_none()
                if sg_obj:
                    group_tag_name = sg_obj.name

            if group_tag_name:
                existing_kw = model.ai_keywords or ""
                if isinstance(existing_kw, list):
                    existing_kw = ", ".join(existing_kw)
                merged_kw = f"{existing_kw}, {group_tag_name}" if existing_kw.strip() else group_tag_name
                model.ai_keywords = merged_kw

            # ── Gắn Tag vào DB (upsert) ───────────────────────────────────
            if model.ai_keywords:
                kw_str = model.ai_keywords if isinstance(model.ai_keywords, str) else ", ".join(model.ai_keywords)
                await _assign_tags_to_model(session, model, kw_str)

            # ── Step 5: Persist results to DB (95%) ───────────────────────
            model.processing_status = ProcessingStatus.completed
            model.processing_error = None
            await session.commit()
            await _add_log(session, model, "Hoàn tất phân tích (95%)", "[95%] Đã lưu kết quả vào CSDL.")

            # ── Step 6: Upload to Target Group (98%) ───────────────────────
            from app.services.settings import SettingsService
            target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
            if not target_chat_str:
                target_chat_str = settings.TELEGRAM_TARGET_CHAT_ID
                
            if target_chat_str:
                try:
                    target_chat_id = int(target_chat_str.strip())
                    try:
                        target_entity = await telegram_client.get_entity(target_chat_id)
                    except Exception:
                        await telegram_client.get_dialogs(limit=100)
                        target_entity = await telegram_client.get_entity(target_chat_id)

                    # Check if tmp_file exists; if missing, re-download
                    if not tmp_file or not os.path.exists(tmp_file):
                        tmp_dir = os.path.join(settings.TEMP_DIR, str(model.id))
                        tmp_file = await download_telegram_document(telegram_client, tg_message, tmp_dir)

                    from telethon.errors import FloodWaitError as UploadFloodWait

                    tag_str = ""
                    if model.ai_keywords:
                        raw_kw = model.ai_keywords
                        kw_list = raw_kw if isinstance(raw_kw, list) else [
                            k.strip() for k in str(raw_kw).replace(',', ' ').split() if k.strip()
                        ]
                        import re as _re
                        hashtags = [
                            "#" + _re.sub(r'[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF]', '_', k).strip('_')
                            for k in kw_list if k
                        ]
                        tag_str = " ".join(hashtags)

                    source_label = f"📢 **Nguồn:** {source_group.name}\n" if source_group else ""
                    studio_line = f"🏷️ **Studio:** #{model.studio_name}\n" if model.studio_name else ""
                    support_badge = "🟢 **[ĐÃ CÓ FILE SUPPORT SẴN]**\n" if model.is_presupported else ""
                    faces_str = f"{model.face_count:,} tris" if model.face_count else f"{model.part_count or 1} part(s)"

                    # Size display in MB / GB
                    raw_size = model.file_size_bytes or 0
                    if raw_size >= 1024 * 1024 * 1024:
                        size_display = f"{raw_size / (1024 * 1024 * 1024):.2f} GB"
                    else:
                        size_display = f"{raw_size / (1024 * 1024):.1f} MB"

                    caption = (
                        f"**{model.predicted_name or model.original_filename}**\n\n"
                        f"{studio_line}"
                        f"{support_badge}"
                        f"📁 **File:** `{model.original_filename}` ({size_display})\n"
                        f"📊 **Quy mô:** {faces_str}\n"
                        f"{source_label}"
                        f"\n{tag_str}"
                    )
                    
                    image_files = []
                    if model.image_paths:
                        for p in model.image_paths:
                            full_p = os.path.join(settings.THUMBNAIL_DIR, p)
                            if os.path.exists(full_p):
                                image_files.append(full_p)
                                
                    # ── CƠ CHẾ FAST-RELAY: Kiểm tra hoặc Forward sang nhóm đích (0.1s, 0MB Upload) ──
                    target_msg_id = model.telegram_target_message_id

                    if not target_msg_id:
                        try:
                            fwd_res = await telegram_client.forward_messages(
                                target_entity,
                                message_id,
                                from_peer=chat_id
                            )
                            if fwd_res:
                                forwarded_doc = fwd_res[0] if isinstance(fwd_res, list) else fwd_res
                                model.telegram_target_message_id = forwarded_doc.id
                                target_msg_id = forwarded_doc.id
                                if forwarded_doc.document:
                                    model.telegram_file_id = str(forwarded_doc.document.id)
                        except Exception as fwd_err:
                            logger.info(f"[{model.id}] Kênh nguồn chặn forward hoặc lỗi ({fwd_err}). Sẽ dùng upload file truyền thống.")

                    if target_msg_id and model.telegram_file_id:
                        # Forward thành công -> BỎ QUA HOÀN TOÀN VIỆC UPLOAD FILE HÀNG GB!
                        await _add_log(session, model, "Backup (98%)", f"[98%] Đã có bản sao lưu chuyển tiếp siêu tốc. Đang đính kèm thông tin mô tả...")
                        if image_files:
                            try:
                                await telegram_client.send_file(
                                    target_entity,
                                    image_files,
                                    caption=caption,
                                    reply_to=target_msg_id
                                )
                            except Exception as album_err:
                                logger.warning(f"Failed to send companion album: {album_err}")
                        else:
                            try:
                                await telegram_client.send_message(
                                    target_entity,
                                    caption,
                                    reply_to=target_msg_id
                                )
                            except Exception as caption_err:
                                logger.warning(f"Failed to send companion caption: {caption_err}")
                    else:
                        # Fallback: Kênh chặn forward -> Bắt buộc upload lại file tmp_file
                        if image_files:
                            await _add_log(session, model, "Backup (98%)", f"[98%] Đang upload album ({len(image_files)} ảnh) + file 3D sang nhóm đích...")

                            upload_retries = 3
                            album_msgs = None
                            for uattempt in range(1, upload_retries + 1):
                                try:
                                    album_msgs = await telegram_client.send_file(
                                        target_entity,
                                        image_files,
                                        caption=caption
                                    )
                                    break
                                except UploadFloodWait as fe:
                                    wait_sec = fe.seconds + 2
                                    logger.warning(f"[FloodWait Upload Album] Chờ {wait_sec}s")
                                    await asyncio.sleep(wait_sec)
                            
                            reply_to_msg_id = album_msgs[0].id if (album_msgs and isinstance(album_msgs, list)) else (album_msgs.id if album_msgs else None)
                            from telethon.tl.types import DocumentAttributeFilename

                            doc_msg = None
                            for uattempt in range(1, upload_retries + 1):
                                try:
                                    doc_msg = await telegram_client.send_file(
                                        target_entity,
                                        tmp_file,
                                        reply_to=reply_to_msg_id,
                                        attributes=[DocumentAttributeFilename(file_name=model.original_filename)]
                                    )
                                    break
                                except UploadFloodWait as fe:
                                    wait_sec = fe.seconds + 2
                                    logger.warning(f"[FloodWait Upload File] Chờ {wait_sec}s")
                                    await asyncio.sleep(wait_sec)

                            if doc_msg:
                                model.telegram_target_message_id = doc_msg.id
                                if doc_msg.document:
                                    model.telegram_file_id = str(doc_msg.document.id)
                        else:
                            await _add_log(session, model, "Backup (98%)", f"[98%] Đang upload file 3D kèm mô tả sang nhóm đích...")

                            upload_retries = 3
                            tg_msg = None
                            for uattempt in range(1, upload_retries + 1):
                                try:
                                    tg_msg = await telegram_client.send_file(
                                        target_entity,
                                        tmp_file,
                                        caption=caption
                                    )
                                    break
                                except UploadFloodWait as fe:
                                    wait_sec = fe.seconds + 2
                                    logger.warning(f"[FloodWait Upload] Chờ {wait_sec}s")
                                    await asyncio.sleep(wait_sec)

                            if tg_msg:
                                model.telegram_target_message_id = tg_msg.id
                                if tg_msg.document:
                                    model.telegram_file_id = str(tg_msg.document.id)

                    await session.commit()
                    await _add_log(session, model, "Backup (99%)", "[99%] Lưu trữ thành công lên nhóm đích.")
                except Exception as upload_exc:
                    err_msg = f"Upload lên nhóm đích ({target_chat_str}) thất bại: {upload_exc}"
                    logger.error(f"[{model.id}] {err_msg}", exc_info=True)
                    model.processing_error = err_msg
                    await _add_log(session, model, "Backup (Lỗi Upload)", f"[Lỗi Upload] {err_msg}")
                    await session.commit()
            else:
                msg_warn = "[Cảnh báo] TELEGRAM_TARGET_CHAT_ID chưa được cài đặt trong System Settings hoặc .env. Bỏ qua upload lưu trữ."
                logger.warning(f"[{model.id}] {msg_warn}")
                await _add_log(session, model, "Backup (Chưa cài ID)", msg_warn)

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
            # ── ALWAYS delete entire tmp_dir (xoá cả file 0-byte orphan) ──
            import shutil
            if 'tmp_dir' in locals() and tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    logger.info(f"[{model.id}] Đã dọn sạch thư mục tạm: {tmp_dir}")
                except Exception as e:
                    logger.warning(f"[{model.id}] Không xóa được tmp_dir {tmp_dir}: {e}")

            # Run a sweep on TEMP_DIR to purge any orphaned leftover temp files
            _cleanup_orphaned_temp_files(settings.TEMP_DIR)


def _cleanup_orphaned_temp_files(temp_dir: str, max_age_seconds: int = 120) -> None:
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



async def process_manual_upload(ctx: dict, model_id: str, filepath: str, **kwargs) -> None:
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
            
            # 3. Fast Mesh Inspection
            await _add_log(session, model, "Đo đạc 3D", "Đang quét nhanh thông số 3D...")
            mesh_info = inspect_3d_file(filepath)
            model.part_count = mesh_info.part_count
            model.is_presupported = mesh_info.is_presupported
            model.face_count = mesh_info.face_count
            
            # 4. Tag with AI
            await _add_log(session, model, "AI Tagger", "Gửi dữ liệu cho AI phân tích Studio & Category...")
            ai_result = await tag_model(
                filename=model.original_filename,
                face_count=mesh_info.face_count,
                message_text=f"Manual Upload: {model.original_filename}",
                is_presupported=mesh_info.is_presupported,
            )
            
            # 5. Update DB
            model.predicted_name = ai_result.predicted_name
            model.studio_name = ai_result.studio
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


async def process_target_message(ctx: dict, message_id: int, chat_id: int, **kwargs) -> None:
    """
    arq task: Import a 3D file that already exists in the TARGET GROUP into DB.

    ⚡ FAST PATH — NO DOWNLOAD:
      1. Fetch message metadata from Telegram (no file download)
      2. Create/update Model3D record with telegram_file_id
      3. Run AI tagging based on filename + caption only
      4. Mark as completed — geometry data left blank (file is already on Telegram)

    This completes in ~2-5 seconds vs ~hours for large file downloads.
    """
    telegram_client = ctx.get("telegram_client")

    if not telegram_client or not telegram_client.is_connected():
        logger.error(f"[TARGET IMPORT #{message_id}] Telegram client không kết nối.")
        return

    model = None

    async with AsyncSessionLocal() as session:
        try:
            # ── Step 1: Fetch message metadata (no download) ───────────────────
            tg_msg = await telegram_client.get_messages(chat_id, ids=message_id)
            if not tg_msg or not tg_msg.document:
                logger.warning(f"[TARGET IMPORT #{message_id}] Không tìm thấy document trong nhóm {chat_id}.")
                return

            # Extract filename and extension
            file_name = "unknown"
            file_ext = ""
            for attr in tg_msg.document.attributes:
                if hasattr(attr, "file_name"):
                    file_name = attr.file_name
                    file_ext = file_name.rsplit(".", 1)[-1].lower()
                    break

            file_size = tg_msg.document.size
            file_id_str = str(tg_msg.document.id)
            caption = tg_msg.message or ""

            # ── Step 2: Check / create Model3D record ─────────────────────────
            stmt_dup = select(Model3D).where(
                (Model3D.telegram_file_id == file_id_str)
                | (
                    (Model3D.original_filename == file_name)
                    & (Model3D.file_size_bytes == file_size)
                )
            )
            existing = (await session.execute(stmt_dup)).scalars().first()

            if existing:
                if existing.processing_status == ProcessingStatus.completed and existing.telegram_file_id:
                    logger.info(f"[TARGET IMPORT #{message_id}] '{file_name}' đã có trong DB, bỏ qua.")
                    return
                model = existing
                model.processing_status = ProcessingStatus.processing
                model.telegram_file_id = file_id_str
                model.telegram_target_message_id = message_id
                model.processing_retries = (model.processing_retries or 0) + 1
            else:
                model = Model3D(
                    original_filename=file_name,
                    file_extension=file_ext,
                    file_size_bytes=file_size,
                    telegram_message_id=message_id,
                    telegram_target_message_id=message_id,
                    telegram_file_id=file_id_str,
                    telegram_message_text=caption[:500] if caption else None,
                    processing_status=ProcessingStatus.processing,
                    processing_retries=1,
                )
                session.add(model)

            await session.commit()
            await session.refresh(model)

            await _add_log(session, model, "Target Import", f"[10%] ⚡ Fast-import msg #{message_id} — '{file_name}' ({file_size/(1024*1024):.1f} MB)")

            # ── Step 3: Fast Remote Header Inspection (< 128KB, ~0.3s) ────────
            from app.services.fast_mesh import inspect_telegram_document_remote
            await _add_log(session, model, "Đo đạc 3D từ xa", "[30%] Đọc header từ xa (STL header / ZIP Central Directory, < 128KB)...")
            mesh_info = await inspect_telegram_document_remote(telegram_client, tg_msg.document, file_name)

            model.face_count = mesh_info.face_count or None
            model.part_count = mesh_info.part_count
            model.is_presupported = mesh_info.is_presupported

            log_parts = []
            if model.face_count:
                log_parts.append(f"{model.face_count:,} faces")
            if model.part_count and model.part_count > 1:
                log_parts.append(f"{model.part_count} parts")
            if model.is_presupported:
                log_parts.append("Pre-supported: Có")
            stats_str = f" ({', '.join(log_parts)})" if log_parts else ""
            await _add_log(session, model, "Đo đạc 3D từ xa", f"[40%] Đã trích xuất thông số 3D{stats_str} thành công.")

            # ── Step 4: AI Tagging (với đầy đủ thông số 3D từ xa) ─────────────
            await _add_log(session, model, "AI Tagger", "[60%] Gửi thông số cho AI phân tích...")

            ai_result = await tag_model(
                filename=file_name,
                face_count=model.face_count,
                message_text=caption,
                is_presupported=model.is_presupported,
            )

            model.predicted_name = ai_result.predicted_name
            model.studio_name = ai_result.studio
            model.ai_category = ai_result.category
            try:
                model.ai_print_type = PrintType(ai_result.print_type)
            except (ValueError, AttributeError):
                model.ai_print_type = PrintType.Unknown
            model.ai_keywords = ai_result.keywords
            model.ai_raw_response = ai_result.raw_response

            if ai_result.keywords:
                await _assign_tags_to_model(session, model, ai_result.keywords)

            # ── Step 5: Mark completed ─────────────────────────────────────────
            model.processing_status = ProcessingStatus.completed
            model.processing_error = None
            await session.commit()

            await _add_log(session, model, "Hoàn tất (100%)", f"[100%] ✅ Fast-import hoàn tất! '{file_name}'{stats_str}")
            logger.info(f"[TARGET IMPORT #{message_id}] ✅ '{file_name}' imported ({stats_str.strip()}).")

        except Exception as exc:
            if model:
                model.processing_status = ProcessingStatus.failed
                model.processing_error = str(exc)
                try:
                    await session.commit()
                except Exception:
                    pass
            logger.error(f"[TARGET IMPORT #{message_id}] ❌ Lỗi: {exc}", exc_info=True)

