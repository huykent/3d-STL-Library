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

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.model3d import DetailLevel, Model3D, PrintType, ProcessingStatus
from app.services.ai_tagger import tag_model
from app.services.stl_analyzer import analyze_mesh
from app.services.thumbnail import render_thumbnail
from app.telegram.downloader import download_telegram_document, extract_3d_files

logger = logging.getLogger(__name__)


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
        stmt = select(Model3D).where(Model3D.telegram_message_id == message_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            logger.info(f"Creating new Model3D record for message_id={message_id}")
            model = Model3D(
                telegram_file_id=str(tg_message.document.id),
                telegram_message_id=message_id,
                source_group_id=internal_sg_id,
                original_filename=file_name,
                file_extension=file_name.split('.')[-1].lower() if '.' in file_name else "",
                file_size_bytes=tg_message.document.size,
                processing_status=ProcessingStatus.processing,
                processing_retries=1
            )
            session.add(model)
            await session.flush()
        else:
            if model.processing_status == ProcessingStatus.completed:
                logger.info(f"Model {model.id} already completed. Skipping re-processing.")
                return
            model.processing_status = ProcessingStatus.processing
            model.processing_retries = (model.processing_retries or 0) + 1
            
        await session.commit()

        try:
            # ── Step 1: Download temp file from Telegram ──────────────────
            tmp_dir = settings.TEMP_DIR
            os.makedirs(tmp_dir, exist_ok=True)

            tmp_file = await download_telegram_document(
                telegram_client, tg_message, save_dir=tmp_dir
            )
            logger.info(f"Downloaded temp file for model {model.id}: {tmp_file}")

            # ── Step 1.5: Extract archive if needed ───────────────────────
            extract_dir = os.path.join(tmp_dir, f"ext_{model.id}")
            extracted_files = await extract_3d_files(tmp_file, extract_dir)
            
            if not extracted_files:
                raise ValueError("No .stl or .obj files found in the archive.")
                
            model.part_count = len(extracted_files)
                
            # Process the first valid 3D file found
            target_3d_file = extracted_files[0]
            logger.info(f"[{model.id}] Target 3D file for analysis: {target_3d_file}")

            # ── Step 2: Analyze mesh geometry ─────────────────────────────
            analysis = analyze_mesh(target_3d_file)
            logger.info(
                f"[{model.id}] Mesh analysis: "
                f"{analysis.face_count:,} faces, "
                f"detail={analysis.detail_level.value}, "
                f"bbox={analysis.bbox_x_mm:.1f}×{analysis.bbox_y_mm:.1f}×{analysis.bbox_z_mm:.1f}mm"
            )

            # ── Step 3: Render thumbnail ───────────────────────────────────
            thumb_filename = f"{model.id}.png"
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_filename)
            render_thumbnail(target_3d_file, thumb_path)
            logger.info(f"[{model.id}] Thumbnail saved: {thumb_path}")

            # ── Step 4: AI Tagging ────────────────────────────────────────
            ai_result = await tag_model(
                filename=model.original_filename,
                face_count=analysis.face_count,
                bbox=(analysis.bbox_x_mm, analysis.bbox_y_mm, analysis.bbox_z_mm),
            )
            logger.info(
                f"[{model.id}] AI tags: "
                f"name={ai_result.predicted_name!r}, "
                f"cat={ai_result.category}, "
                f"type={ai_result.print_type}, "
                f"keywords={ai_result.keywords}"
            )

            # ── Step 5: Persist results to DB ─────────────────────────────
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
            await session.commit()
            
            logger.info(f"[{model.id}] Processing completed successfully.")

            # ── Step 6: Upload to Target Group ─────────────────────────────
            from app.services.settings import SettingsService
            target_chat_str = await SettingsService.get_setting("TELEGRAM_TARGET_CHAT_ID")
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
                    await telegram_client.send_file(
                        target_chat_id, 
                        tmp_file, 
                        thumb=thumb_path if os.path.exists(thumb_path) else None,
                        caption=caption
                    )
                    logger.info(f"[{model.id}] Successfully backed up file to target group {target_chat_id}")
                except Exception as upload_exc:
                    logger.error(f"[{model.id}] Failed to upload to target group: {upload_exc}")

        except Exception as exc:
            logger.error(
                f"[{model.id}] Pipeline error: {exc}",
                exc_info=True,
            )
            model.processing_status = ProcessingStatus.failed
            model.processing_error = str(exc)
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
                    logger.info(f"[{model.id}] Deleted temp file: {tmp_file}")
                except OSError as e:
                    logger.warning(f"[{model.id}] Could not delete temp file {tmp_file}: {e}")
            if 'extract_dir' in locals() and os.path.exists(extract_dir):
                try:
                    shutil.rmtree(extract_dir)
                    logger.info(f"[{model.id}] Deleted extract dir: {extract_dir}")
                except OSError as e:
                    logger.warning(f"[{model.id}] Could not delete extract dir {extract_dir}: {e}")

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
            extracted_files = await extract_3d_files(filepath, extract_dir)
            if not extracted_files:
                raise ValueError("No .stl or .obj files found in the archive.")
                
            model.part_count = len(extracted_files)
            target_3d_file = extracted_files[0]
            
            # 2. Upload to Telegram to get telegram_message_id and file_id
            # Get the backup chat id (either TELEGRAM_BACKUP_CHAT_ID or first from chat_ids)
            backup_chat_str = os.environ.get("TELEGRAM_BACKUP_CHAT_ID")
            if backup_chat_str:
                backup_chat_id = int(backup_chat_str.strip())
            else:
                chats = settings.chat_ids
                if not chats:
                    raise ValueError("No Telegram chat IDs configured for backup.")
                backup_chat_id = chats[0]
            
            logger.info(f"[{model.id}] Uploading manual file to Telegram backup group {backup_chat_id}...")
            tg_message = await telegram_client.send_file(
                backup_chat_id, 
                filepath, 
                caption=f"Manual Upload: {model.original_filename}"
            )
            model.telegram_message_id = tg_message.id
            model.telegram_file_id = str(tg_message.document.id)
            
            # 3. Analyze Mesh
            analysis = analyze_mesh(target_3d_file)
            
            # 4. Render Thumbnail
            thumb_filename = f"{model.id}.png"
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_filename)
            render_thumbnail(target_3d_file, thumb_path)
            
            # 5. Tag with AI
            ai_result = await tag_model(
                filename=model.original_filename,
                face_count=analysis.face_count,
                bbox=(analysis.bbox_x_mm, analysis.bbox_y_mm, analysis.bbox_z_mm),
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
            await session.commit()
            logger.info(f"[{model.id}] Manual processing completed successfully.")

        except Exception as exc:
            logger.error(f"[{model.id}] Manual pipeline error: {exc}", exc_info=True)
            model.processing_status = ProcessingStatus.failed
            model.processing_error = str(exc)
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
