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
    CHUNK_SIZE = 512 * 1024  # 512 KB — chunk size chuẩn của Telethon iter_download
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

        except Exception:
            raise

    raise RuntimeError(f"Tải file '{file_name}' thất bại sau {max_retries} lần thử (FloodWait liên tục)")


