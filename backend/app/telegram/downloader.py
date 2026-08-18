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
    CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB — Telegram Premium cho phép chunk lớn hơn, throughput cao hơn
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

    # ── Tải bằng Parallel Multi-Worker (Fast Download IDM Style) ──────────────
    max_retries = 5
    PARALLEL_WORKERS = 8  # 8 luồng tải song song cùng lúc
    RPC_CHUNK_SIZE = 512 * 1024  # 512 KB — Hạn mức tối đa 1 RPC request Telegram cho phép

    for attempt in range(1, max_retries + 1):
        try:
            # Nếu file chưa tồn tại, khởi tạo file với dung lượng total_size
            if not os.path.exists(save_path):
                with open(save_path, 'wb') as _f_init:
                    if total_size > 0:
                        _f_init.truncate(total_size)

            if total_size > 0 and total_size >= 10 * 1024 * 1024:
                # Với file >= 10MB: Dùng Parallel Multi-Worker Bứt Tốc (20-40 MB/s)
                logger.info(f"[FastDownload] Sử dụng {PARALLEL_WORKERS} luồng song song cho file '{file_name}' ({total_size/(1024*1024):.1f} MB)")
                
                from telethon import utils
                from telethon.tl.functions.upload import GetFileRequest

                location = utils.get_input_location(message.document)
                total_chunks = (total_size + RPC_CHUNK_SIZE - 1) // RPC_CHUNK_SIZE
                start_chunk = existing_size // RPC_CHUNK_SIZE
                
                downloaded_counter = [existing_size]
                lock = asyncio.Lock()

                queue = asyncio.Queue()
                for c_idx in range(start_chunk, total_chunks):
                    offset = c_idx * RPC_CHUNK_SIZE
                    queue.put_nowait((c_idx, offset))

                async def _worker():
                    while not queue.empty():
                        try:
                            c_idx, offset = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                        try:
                            res = await client(GetFileRequest(
                                location=location,
                                offset=offset,
                                limit=RPC_CHUNK_SIZE
                            ))
                            if res and res.bytes:
                                chunk_bytes = res.bytes
                                async with lock:
                                    with open(save_path, 'r+b') as f_out:
                                        f_out.seek(offset)
                                        f_out.write(chunk_bytes)
                                    downloaded_counter[0] += len(chunk_bytes)
                                    if progress_callback:
                                        progress_callback(downloaded_counter[0], total_size)
                        except Exception as worker_err:
                            # Re-queue để worker khác tải lại
                            await queue.put((c_idx, offset))
                            raise worker_err
                        finally:
                            queue.task_done()

                workers = [asyncio.create_task(_worker()) for _ in range(PARALLEL_WORKERS)]
                await asyncio.gather(*workers)

            else:
                # File < 10MB hoặc fallback: Tải bằng iter_download chuẩn
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
                    existing_size = 0
                    raise RuntimeError(
                        f"Download incomplete: expected {total_size:,}, got {actual_size:,} bytes"
                    )

            logger.info(f"[Download] Hoàn tất: '{file_name}' ({os.path.getsize(save_path):,} bytes)")
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
            if os.path.exists(save_path):
                raw_size = os.path.getsize(save_path)
                existing_size = (raw_size // CHUNK_SIZE) * CHUNK_SIZE
                with open(save_path, 'r+b') as _f:
                    _f.truncate(existing_size)

        except RuntimeError:
            if attempt >= max_retries:
                raise RuntimeError(f"Tải file '{file_name}' thất bại sau {max_retries} lần thử (size mismatch liên tục)")
            await asyncio.sleep(2)

        except Exception as e:
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
                # Lỗi khác khi tải song song: log warning và fallback về iter_download ở lượt thử kế
                logger.warning(f"[ParallelDownload Warning] Gặp lỗi {e}, chuyển về chế độ tải tiêu chuẩn...")
                await asyncio.sleep(1)

    raise RuntimeError(f"Tải file '{file_name}' thất bại sau {max_retries} lần thử (FloodWait liên tục)")

