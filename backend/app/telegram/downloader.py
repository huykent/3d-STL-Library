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

_SENDER_CONNECT_LOCK = asyncio.Lock()

async def fast_download_document(
    client,
    message,
    save_path: str,
    progress_callback=None,
    status_callback=None,
    connection_count: int = 4,
) -> bool:
    """
    High-Speed Parallel MTProto Downloader (Telethon Multi-Sender).
    - Connection Mutex Lock prevents race conditions during _borrow_exported_sender.
    - Multi-tier timeouts (6s connect, 10s chunk, overall file timeout) prevent stalls.
    - Non-blocking file I/O so disk writes never block asyncio loop.
    """
    import math
    from telethon import utils
    from telethon.tl.functions.upload import GetFileRequest

    doc = message.document
    total_size = doc.size or 0
    if total_size <= 0:
        return False

    file_name = os.path.basename(save_path)
    safe_connections = min(max(1, connection_count), 4)
    logger.info(f"[FastDownload] 🚀 Khởi tạo {safe_connections} luồng song song tới Telegram DC cho '{file_name}' ({total_size / (1024*1024):.1f} MB)...")
    if status_callback:
        await status_callback(f"[Siêu tốc] Khởi tạo {safe_connections} luồng tải song song...")

    try:
        dc_id, location = utils.get_input_location(doc)
    except Exception as e:
        logger.warning(f"[FastDownload] Không thể lấy DC location: {e}. Fallback về tiêu chuẩn.")
        return False

    # Pre-allocate output file size
    try:
        with open(save_path, 'wb') as f:
            f.seek(total_size - 1)
            f.write(b'\0')
    except Exception as e:
        logger.warning(f"[FastDownload] Không thể tạo file đích: {e}")
        return False

    part_size = 512 * 1024  # 512 KB per request (standard Telegram chunk)
    parts_count = math.ceil(total_size / part_size)

    queue = asyncio.Queue()
    for i in range(parts_count):
        queue.put_nowait(i)

    downloaded = 0
    active = True
    progress_lock = asyncio.Lock()

    # Open file descriptor for direct non-overlapping writes
    fd = os.open(save_path, os.O_RDWR | getattr(os, 'O_BINARY', 0))

    def _write_part(offset: int, data: bytes):
        try:
            if hasattr(os, 'pwrite'):
                os.pwrite(fd, data, offset)
            else:
                os.lseek(fd, offset, os.SEEK_SET)
                os.write(fd, data)
        except Exception as we:
            logger.error(f"[FastDownload Write Error] {we}")

    async def _safe_borrow_sender():
        """Borrow sender with mutex lock and strict 6s timeout."""
        async with _SENDER_CONNECT_LOCK:
            return await asyncio.wait_for(client._borrow_exported_sender(dc_id), timeout=6.0)

    async def _safe_cleanup_sender(sender_obj):
        """Cleanly return or disconnect an exported sender without leaving pending tasks."""
        if not sender_obj:
            return
        try:
            await client._return_exported_sender(sender_obj)
        except Exception:
            try:
                await sender_obj.disconnect()
            except Exception:
                pass

    async def worker_loop():
        nonlocal downloaded, active
        sender = None
        consecutive_errors = 0

        # Borrow initial sender with lock and timeout
        try:
            sender = await _safe_borrow_sender()
        except Exception as be:
            logger.warning(f"[FastDownload] Không thể mượn sender ban đầu: {be}")
            return

        try:
            while active and not queue.empty():
                try:
                    part_idx = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                offset = part_idx * part_size
                limit = min(part_size, total_size - offset)
                part_downloaded = False

                for attempt in range(3):
                    if not active:
                        break

                    if sender is None or consecutive_errors >= 2:
                        if sender:
                            await _safe_cleanup_sender(sender)
                            sender = None
                        try:
                            sender = await _safe_borrow_sender()
                            consecutive_errors = 0
                        except Exception as re_err:
                            logger.warning(f"[FastDownload] Tái kết nối sender thất bại: {re_err}")
                            await asyncio.sleep(1.0)
                            continue

                    try:
                        # Strict 10s timeout to prevent hanging TCP connections
                        res = await asyncio.wait_for(
                            sender.send(GetFileRequest(location, offset=offset, limit=limit)),
                            timeout=10.0
                        )

                        if res and hasattr(res, 'bytes') and res.bytes:
                            chunk_data = res.bytes
                            await asyncio.to_thread(_write_part, offset, chunk_data)

                            async with progress_lock:
                                downloaded += len(chunk_data)
                                if progress_callback:
                                    try:
                                        progress_callback(downloaded, total_size)
                                    except Exception:
                                        pass

                            consecutive_errors = 0
                            part_downloaded = True
                            break
                        else:
                            consecutive_errors += 1
                    except asyncio.TimeoutError:
                        consecutive_errors += 1
                        logger.warning(f"[FastDownload] Chunk {part_idx} ({offset//1024}KB) timed out (10s). Thử lại...")
                        if sender:
                            await _safe_cleanup_sender(sender)
                            sender = None
                        await asyncio.sleep(0.5)
                    except Exception as exc:
                        err_str = str(exc)
                        consecutive_errors += 1
                        if 'FLOOD' in err_str.upper():
                            await asyncio.sleep(3.0)
                        else:
                            await asyncio.sleep(0.5)

                if not part_downloaded and active:
                    queue.put_nowait(part_idx)
                    if consecutive_errors >= 5:
                        logger.warning(f"[FastDownload] Worker gặp quá nhiều lỗi liên tiếp. Dừng luồng này.")
                        break

        finally:
            if sender:
                await _safe_cleanup_sender(sender)

    workers = []
    try:
        workers = [asyncio.create_task(worker_loop()) for _ in range(safe_connections)]
        # Dynamic overall timeout: 60s base + 3s per MB, capped between 60s and 1800s
        overall_timeout = max(60.0, min(1800.0, (total_size / (1024 * 1024)) * 3.0))
        await asyncio.wait_for(asyncio.gather(*workers), timeout=overall_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"[FastDownload] Tải đa luồng cho '{file_name}' vượt quá thời gian cho phép ({overall_timeout:.0f}s). Hủy FastDownload...")
        active = False
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    except Exception as ge:
        logger.warning(f"[FastDownload Exception] {ge}")
        active = False
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    finally:
        try:
            os.close(fd)
        except Exception:
            pass

    actual_size = os.path.getsize(save_path) if os.path.exists(save_path) else 0
    if total_size > 0 and actual_size == total_size and downloaded >= total_size:
        logger.info(f"[FastDownload] ✅ Hoàn tất siêu tốc: '{file_name}' ({actual_size:,} bytes)")
        return True
    else:
        try:
            if os.path.exists(save_path):
                os.unlink(save_path)
        except Exception:
            pass
        logger.warning(f"[FastDownload] Tải đa luồng chưa đủ dữ liệu ({downloaded} vs {total_size} bytes). Chuyển về chế độ chuẩn...")
        return False


async def download_telegram_document(client, message, save_dir: str, progress_callback=None, status_callback=None) -> str:
    """
    Download a document from a Telegram message to the given directory.
    ✅ FastTelethon High-Speed Multi-Connection Download (Telegram Premium optimized).
    ✅ Resumable: nếu file đang tải bị gián đoạn (worker restart, crash...) thì
       tự động tải tiếp từ byte đã có thay vì tải lại từ đầu.
    ✅ Verify size: sau khi tải xong, kiểm tra kích thước thực tế vs kỳ vọng.
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

    # ── Kiểm tra file tạm đã hoàn chỉnh ─────────────────────────────────────
    if os.path.exists(save_path):
        raw_size = os.path.getsize(save_path)
        if total_size > 0 and raw_size >= total_size:
            logger.info(f"[Resume] File '{file_name}' đã có đầy đủ ({raw_size} bytes). Bỏ qua tải lại.")
            return save_path

    # ── Thử tải bằng FastTelethon (đa luồng song song dành cho Telegram Premium) ─────
    if total_size > 5 * 1024 * 1024:  # Áp dụng cho file > 5 MB
        try:
            ok = await fast_download_document(
                client,
                message,
                save_path,
                progress_callback=progress_callback,
                status_callback=status_callback,
                connection_count=4,
            )
            if ok:
                return save_path
        except Exception as e:
            logger.warning(f"[FastDownload Exception] {e}. Chuyển về chế độ iter_download tiêu chuẩn.")

    # ── Fallback: Tải (hoặc tải tiếp) bằng iter_download chuẩn Telethon có timeout từng chunk ──────
    CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB
    existing_size = 0
    if os.path.exists(save_path):
        raw_size = os.path.getsize(save_path)
        existing_size = (raw_size // CHUNK_SIZE) * CHUNK_SIZE
        if existing_size > 0:
            with open(save_path, 'r+b') as _f:
                _f.truncate(existing_size)

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            file_mode = 'ab' if existing_size > 0 else 'wb'
            downloaded = existing_size

            with open(save_path, file_mode) as f:
                gen = client.iter_download(
                    message.document,
                    offset=existing_size,
                    chunk_size=CHUNK_SIZE,
                    request_size=CHUNK_SIZE,
                ).__aiter__()

                while True:
                    try:
                        # Wrap per-chunk retrieval in strict 15s timeout
                        chunk = await asyncio.wait_for(gen.__anext__(), timeout=15.0)
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
                    except StopAsyncIteration:
                        break

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

            logger.info(f"[Download] Hoàn tất: '{file_name}' ({downloaded:,} bytes)")
            return save_path

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

