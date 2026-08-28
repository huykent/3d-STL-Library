import pytest
from app.worker.queue import get_redis_pool

@pytest.mark.asyncio
async def test_get_redis_pool():
    pool = await get_redis_pool()
    assert pool is not None
    # close pool to avoid leaks
    await pool.close()
