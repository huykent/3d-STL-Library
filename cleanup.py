#!/usr/bin/env python3
"""
Maintenance script: chạy trực tiếp trên VPS trong container api/worker.
Dọn zombie models (stuck processing) và xóa model thất bại không phục hồi được.

Dùng:
  docker exec stl_api python /tmp/cleanup.py --dry-run    # xem trước
  docker exec stl_api python /tmp/cleanup.py               # thực thi
  docker exec stl_api python /tmp/cleanup.py --reset-all   # reset ALL processing→pending ngay
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta, timezone

DRY_RUN = "--dry-run" in sys.argv
RESET_ALL = "--reset-all" in sys.argv  # Reset toàn bộ processing→pending, bỏ qua time check

# ── Thời gian giới hạn: model processing > N phút → zombie ─────────────────
STUCK_MINUTES = 15          # Nếu processing > 15 phút → zombie → reset về pending
MAX_RETRIES = 5             # Nếu retried >= 5 lần → không cứu được → xóa
FAILED_KEEP_DAYS = 7        # Model failed > 7 ngày → xóa

async def main():
    # Load settings từ env của container
    sys.path.insert(0, "/app")
    from app.database import AsyncSessionLocal
    from app.models.model3d import Model3D, ProcessingStatus
    from sqlalchemy import select, delete, func, update

    print("=" * 60)
    print("  3D STL Library — Database Maintenance")
    print(f"  Mode: {'DRY RUN (không thay đổi gì)' if DRY_RUN else '⚠️  LIVE (thực thi)'}")
    if RESET_ALL:
        print("  ⚡ --reset-all: Reset TẤT CẢ processing → pending")
    print("=" * 60)

    async with AsyncSessionLocal() as session:

        # ── 1. Thống kê hiện tại ─────────────────────────────────────────────
        print("\n📊 Thống kê hiện tại:")
        for status in ProcessingStatus:
            count = (await session.execute(
                select(func.count()).where(Model3D.processing_status == status)
            )).scalar()
            print(f"   {status.value:12s}: {count:,}")

        total = (await session.execute(select(func.count(Model3D.id)))).scalar()
        print(f"   {'TOTAL':12s}: {total:,}")

        # ── 2. Zombie models: stuck in "processing" > STUCK_MINUTES ─────────
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC
        cutoff_zombie = now_utc - timedelta(minutes=STUCK_MINUTES)

        if RESET_ALL:
            # Reset ALL processing models regardless of time
            all_processing_q = await session.execute(
                select(Model3D).where(Model3D.processing_status == ProcessingStatus.processing)
            )
            zombies = all_processing_q.scalars().all()
            print(f"\n⚡ --reset-all: Tìm thấy {len(zombies)} model đang processing (sẽ reset hết)")
        else:
            zombie_q = await session.execute(
                select(Model3D).where(
                    Model3D.processing_status == ProcessingStatus.processing,
                    Model3D.updated_at < cutoff_zombie
                )
            )
            zombies = zombie_q.scalars().all()
            print(f"\n🧟 Zombie models (processing > {STUCK_MINUTES} phút): {len(zombies)}")

        reset_to_pending = []
        mark_failed = []
        for m in zombies:
            age_min = int((datetime.utcnow() - m.updated_at).total_seconds() / 60)
            if m.processing_retries >= MAX_RETRIES:
                mark_failed.append(m)
                print(f"   ❌ [{age_min}m stuck, {m.processing_retries} retries] {m.original_filename}")
            else:
                reset_to_pending.append(m)
                print(f"   🔄 [{age_min}m stuck, {m.processing_retries} retries] {m.original_filename}")

        # ── 3. Permanently failed: retries >= MAX_RETRIES ───────────────────
        perm_failed_q = await session.execute(
            select(Model3D).where(
                Model3D.processing_status == ProcessingStatus.failed,
                Model3D.processing_retries >= MAX_RETRIES
            )
        )
        perm_failed = perm_failed_q.scalars().all()
        print(f"\n💀 Permanently failed (>= {MAX_RETRIES} retries): {len(perm_failed)}")
        for m in perm_failed[:10]:
            print(f"   🗑️  [{m.processing_retries} retries] {m.original_filename}")
        if len(perm_failed) > 10:
            print(f"   ... và {len(perm_failed)-10} model khác")

        # ── 4. Old failed: failed > FAILED_KEEP_DAYS days ───────────────────
        cutoff_old = now_utc - timedelta(days=FAILED_KEEP_DAYS)
        old_failed_q = await session.execute(
            select(Model3D).where(
                Model3D.processing_status == ProcessingStatus.failed,
                Model3D.updated_at < cutoff_old
            )
        )
        old_failed = old_failed_q.scalars().all()
        # Merge, dedup
        to_delete_ids = list({m.id for m in perm_failed} | {m.id for m in old_failed})
        print(f"\n🗑️  Tổng model sẽ XÓA: {len(to_delete_ids)}")

        # ── 5. Thực thi ──────────────────────────────────────────────────────
        if DRY_RUN:
            print("\n⏸️  DRY RUN — không thay đổi gì. Chạy lại không có --dry-run để áp dụng.")
        else:
            # Reset zombies → pending (để worker retry)
            if reset_to_pending:
                for m in reset_to_pending:
                    m.processing_status = ProcessingStatus.pending
                    m.processing_retries = (m.processing_retries or 0) + 1
                    m.processing_error = f"Reset from zombie (stuck >{STUCK_MINUTES}m)"
                print(f"   ✅ Reset {len(reset_to_pending)} zombie → pending")

            # Mark unrecoverable zombies as failed
            if mark_failed:
                for m in mark_failed:
                    m.processing_status = ProcessingStatus.failed
                    m.processing_error = f"Zombie: max retries ({MAX_RETRIES}) exceeded"
                print(f"   ✅ Đánh failed {len(mark_failed)} zombie không phục hồi")

            # Delete permanently failed + old failed
            if to_delete_ids:
                await session.execute(
                    delete(Model3D).where(Model3D.id.in_(to_delete_ids))
                )
                print(f"   ✅ Đã xóa {len(to_delete_ids)} model thất bại")

            await session.commit()
            print("\n✅ Commit xong. Tất cả thay đổi đã được lưu.")

        # ── 6. Thống kê sau dọn ──────────────────────────────────────────────
        if not DRY_RUN:
            print("\n📊 Thống kê sau dọn:")
            for status in ProcessingStatus:
                count = (await session.execute(
                    select(func.count()).where(Model3D.processing_status == status)
                )).scalar()
                print(f"   {status.value:12s}: {count:,}")

    print("\n" + "=" * 60)
    print("  Hoàn tất!")
    print("=" * 60)

asyncio.run(main())
