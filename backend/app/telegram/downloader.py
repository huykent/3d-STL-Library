import os
import patoolib
import asyncio
import logging

logger = logging.getLogger(__name__)

async def extract_3d_files(file_path: str, extract_dir: str) -> list[str]:
    """
    Extract an archive and return paths to all .stl and .obj files inside.
    If the file is already a .stl/.obj, it just returns a list with that file.
    """
    file_ext = file_path.split('.')[-1].lower()
    
    if file_ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene']:
        return [file_path]
        
    os.makedirs(extract_dir, exist_ok=True)
    
    # Run patoolib extraction in a thread to avoid blocking asyncio
    await asyncio.to_thread(patoolib.extract_archive, file_path, outdir=extract_dir, verbosity=-1)
    
    extracted_3d_files = []
    all_files_found = []
    for root, _, files in os.walk(extract_dir):
        for file in files:
            all_files_found.append(file)
            ext = file.split('.')[-1].lower()
            if ext in ['stl', 'obj', '3mf', 'pm7m', 'pwscene']:
                extracted_3d_files.append(os.path.join(root, file))
                
    # Sort extracted 3D files by file size descending so the main/largest 3D model is selected first
    extracted_3d_files.sort(key=lambda f: os.path.getsize(f), reverse=True)
                
    if not extracted_3d_files:
        import logging
        logging.getLogger(__name__).warning(f"No 3D files found. Files in archive: {all_files_found}")
        
    return extracted_3d_files

async def download_telegram_document(client, message, save_dir: str, progress_callback=None, status_callback=None) -> str:
    """
    Download a document from a Telegram message to the given directory.
    ✅ Resumable: nếu file đang tải bị gián đoạn (worker restart, crash...) thì
       tự động tải tiếp từ byte đã có thay vì tải lại từ đầu.
    ✅ Verify size: sau khi tải xong, kiểm tra kích thước thực tế vs kỳ vọng.
       Nếu lệch (bị cắt ngang) → xóa và raise để worker retry.
    ✅ Handles Telegram FloodWait/rate-limit với retry + tự động chờ.
    Returns the absolute path to the downloaded file.
    """
    from telethon.errors import FloodWaitError

    os.makedirs(save_dir, exist_ok=True)

    # ── Xác định tên file từ attributes ─────────────────────────────────────
    file_name = None
    for attr in message.document.attributes:
        if hasattr(attr, 'file_name') and attr.file_name:
            file_name = attr.file_name
            break
    if not file_name:
        file_name = f"tg_{message.document.id}"

    save_path = os.path.join(save_dir, file_name)
    total_size: int = message.document.size or 0

    # ── Kiểm tra file tạm đang tải dở ───────────────────────────────────────
    CHUNK_SIZE = 1024 * 1024  # 1 MB — Premium account cho phép chunk lớn hơn
    existing_size = 0
    if os.path.exists(save_path):
        raw_size = os.path.getsize(save_path)
        if total_size > 0 and raw_size >= total_size:
            logger.info(f"[Resume] File '{file_name}' đã có đầy đủ ({raw_size} bytes). Bỏ qua tải lại.")
            return save_path
        # Căn chỉnh về biên chunk để tránh lỗi dữ liệu
        existing_size = (raw_size // CHUNK_SIZE) * CHUNK_SIZE
        if existing_size > 0:
            # Truncate về biên chunk an toàn
            with open(save_path, 'r+b') as _f:
                _f.truncate(existing_size)
            logger.info(
                f"[Resume] File '{file_name}' đang tải dở ({raw_size:,} / {total_size:,} bytes). "
                f"Tiếp tục từ byte {existing_size:,}..."
            )
            if status_callback:
                await status_callback(
                    f"[Tiếp tục] Phát hiện file tải dở ({existing_size/(1024*1024):.1f} MB / "
                    f"{total_size/(1024*1024):.1f} MB), đang tải tiếp..."
                )

    # ── Tải (hoặc tải tiếp) bằng iter_download ──────────────────────────────
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            file_mode = 'ab' if existing_size > 0 else 'wb'
            downloaded = existing_size

            with open(save_path, file_mode) as f:
                async for chunk in client.iter_download(
                    message.document,
                    offset=existing_size,
                    chunk_size=CHUNK_SIZE,
                    request_size=CHUNK_SIZE,
                ):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

            # ── Xác minh kích thước sau khi tải xong ─────────────────────
            # Tránh file bị cắt ngang (như các file 13,107,200 bytes = đúng 25 chunk)
            if total_size > 0:
                actual_size = os.path.getsize(save_path)
                if actual_size != total_size:
                    logger.warning(
                        f"[Download] File '{file_name}' bị cắt ngắn: "
                        f"kỳ vọng {total_size:,} bytes, thực tế {actual_size:,} bytes. "
                        f"Xóa và thử lại (lần {attempt}/{max_retries})..."
                    )
                    try:
                        os.unlink(save_path)
                    except OSError:
                        pass
                    existing_size = 0  # Force fresh download next attempt
                    raise RuntimeError(
                        f"Download incomplete: expected {total_size:,}, got {actual_size:,} bytes"
                    )

            logger.info(f"[Download] Hoàn tất: '{file_name}' ({downloaded:,} bytes)")
            return save_path

        except FloodWaitError as e:
            wait_sec = e.seconds + 2
            logger.warning(
                f"[FloodWait] Telegram yêu cầu chờ {e.seconds}s. "
                f"Tự động chờ {wait_sec}s rồi thử lại (lần {attempt}/{max_retries})..."
            )
            if status_callback:
                await status_callback(
                    f"[Tạm dừng] Telegram yêu cầu chờ {e.seconds}s, "
                    f"tự động nối lại sau {wait_sec}s..."
                )
            await asyncio.sleep(wait_sec)
            # Cập nhật lại kích thước hiện có (có thể đã ghi thêm một ít trước khi lỗi)
            if os.path.exists(save_path):
                raw_size = os.path.getsize(save_path)
                existing_size = (raw_size // CHUNK_SIZE) * CHUNK_SIZE
                with open(save_path, 'r+b') as _f:
                    _f.truncate(existing_size)

        except RuntimeError:
            # RuntimeError từ size mismatch — tiếp tục vòng lặp retry
            if attempt >= max_retries:
                raise RuntimeError(f"Tải file '{file_name}' thất bại sau {max_retries} lần thử (size mismatch liên tục)")
            await asyncio.sleep(2)

        except Exception as e:
            # Xử lý FLOOD_PREMIUM_WAIT (non-premium rate limit — khác với FloodWaitError thông thường)
            err_str = str(e)
            if 'FLOOD_PREMIUM_WAIT' in err_str:
                import re as _re
                m = _re.search(r'FLOOD_PREMIUM_WAIT_(\d+)', err_str)
                wait_sec = int(m.group(1)) + 5 if m else 60
                logger.warning(
                    f"[FLOOD_PREMIUM_WAIT] Telegram giới hạn tốc độ non-premium: chờ {wait_sec}s "
                    f"(lần {attempt}/{max_retries})..."
                )
                if status_callback:
                    await status_callback(
                        f"[Tạm dừng] Telegram yêu cầu Premium, chờ {wait_sec}s rồi thử lại..."
                    )
                await asyncio.sleep(wait_sec)
                if os.path.exists(save_path):
                    raw_size = os.path.getsize(save_path)
                    existing_size = (raw_size // CHUNK_SIZE) * CHUNK_SIZE
                    with open(save_path, 'r+b') as _f:
                        _f.truncate(existing_size)
            else:
                raise

    raise RuntimeError(f"Tải file '{file_name}' thất bại sau {max_retries} lần thử (FloodWait liên tục)")
