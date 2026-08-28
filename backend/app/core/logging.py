import logging
import asyncio
import json
from datetime import datetime
class RedisPubSubHandler(logging.Handler):
    """
    A custom logging handler that publishes log records to a Redis Pub/Sub channel.
    Uses asyncio.create_task to publish without blocking the main thread.
    """
    def __init__(self, process_name: str, channel: str = "system_logs_channel"):
        super().__init__()
        self.process_name = process_name
        self.channel = channel
        self.setFormatter(logging.Formatter('%(message)s'))

    def emit(self, record):
        try:
            msg = self.format(record)
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "process": self.process_name,
                "message": msg,
                "logger": record.name
            }
            
            # Use asyncio to publish. We must handle cases where loop is running.
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(self._publish(log_data))
                # Hold a strong reference to avoid "Task was destroyed but it is pending!" error
                if not hasattr(self, "_bg_tasks"):
                    self._bg_tasks = set()
                self._bg_tasks.add(task)
                task.add_done_callback(self._bg_tasks.discard)
            except RuntimeError:
                # No running loop, skip logging to redis for this event
                pass
        except Exception:
            self.handleError(record)

    async def _publish(self, log_data: dict):
        try:
            from app.worker.queue import get_redis_pool
            redis = await get_redis_pool()
            await redis.publish(self.channel, json.dumps(log_data))
        except Exception:
            pass

def setup_redis_logging(process_name: str):
    """
    Attach the Redis handler to the root logger and set INFO levels for app packages.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    logging.getLogger("app").setLevel(logging.INFO)
    
    # Check if we already added it to prevent duplicates
    for handler in root_logger.handlers:
        if isinstance(handler, RedisPubSubHandler):
            return
            
    redis_handler = RedisPubSubHandler(process_name=process_name)
    redis_handler.setLevel(logging.INFO)
    root_logger.addHandler(redis_handler)
