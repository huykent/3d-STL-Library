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
from app.telegram.downloader import download_telegram_document

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
        # ── Find existing Model3D record ──────────────────────────────────
        stmt = select(Model3D).where(Model3D.telegram_message_id == message_id)
        result = await session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            logger.warning(
                f"No Model3D record found for message_id={message_id}. "
                "The Telegram handler may not have created it yet. Skipping."
            )
            return

        if model.processing_status == ProcessingStatus.completed:
            logger.info(f"Model {model.id} already completed. Skipping re-processing.")
            return

        # Mark as processing and increment retry counter
        model.processing_status = ProcessingStatus.processing
        model.processing_retries = (model.processing_retries or 0) + 1
        await session.commit()

        try:
            # ── Step 1: Download temp file from Telegram ──────────────────
            tmp_dir = settings.TEMP_DIR
            os.makedirs(tmp_dir, exist_ok=True)

            # Fetch the Telegram message object (needed to access .document)
            tg_message = await telegram_client.get_messages(chat_id, ids=message_id)
            tmp_file = await download_telegram_document(
                telegram_client, tg_message, save_dir=tmp_dir
            )
            logger.info(f"Downloaded temp file for model {model.id}: {tmp_file}")

            # ── Step 2: Analyze mesh geometry ─────────────────────────────
            analysis = analyze_mesh(tmp_file)
            logger.info(
                f"[{model.id}] Mesh analysis: "
                f"{analysis.face_count:,} faces, "
                f"detail={analysis.detail_level.value}, "
                f"bbox={analysis.bbox_x_mm:.1f}×{analysis.bbox_y_mm:.1f}×{analysis.bbox_z_mm:.1f}mm"
            )

            # ── Step 3: Render thumbnail ───────────────────────────────────
            thumb_filename = f"{model.id}.png"
            thumb_path = os.path.join(settings.THUMBNAIL_DIR, thumb_filename)
            render_thumbnail(tmp_file, thumb_path)
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
            # ── ALWAYS delete temp file ───────────────────────────────────
            if tmp_file and os.path.exists(tmp_file):
                try:
                    os.unlink(tmp_file)
                    logger.info(f"[{model.id}] Deleted temp file: {tmp_file}")
                except OSError as e:
                    logger.warning(f"[{model.id}] Could not delete temp file {tmp_file}: {e}")
