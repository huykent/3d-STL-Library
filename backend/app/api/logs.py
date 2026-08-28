import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.worker.queue import get_redis_pool
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/stream")
async def websocket_logs_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    await pubsub.subscribe("system_logs_channel")
    
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)
            
            # Simple heartbeat to keep connection alive and detect disconnects
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe("system_logs_channel")
        await pubsub.close()
