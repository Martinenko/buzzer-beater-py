from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
import asyncio
import json
import logging

try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None
    logging.info("redis.asyncio not available; running without Redis pub/sub")


class ConnectionManager:
    def __init__(self):
        # user_id (UUID string) -> set of WebSocket
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self.active_connections.get(user_id)
            if not conns:
                conns = set()
                self.active_connections[user_id] = conns
            conns.add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self.active_connections.get(user_id)
            if not conns:
                return
            conns.discard(websocket)
            if len(conns) == 0:
                self.active_connections.pop(user_id, None)

    async def send_json_to_user(self, user_id: str, data) -> None:
        conns = self.active_connections.get(user_id)
        if not conns:
            return
        to_remove = []
        for ws in list(conns):
            try:
                await ws.send_json(data)
            except Exception:
                to_remove.append(ws)
        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    conns.discard(ws)
                if len(conns) == 0:
                    self.active_connections.pop(user_id, None)

    async def publish(self, channel: str, message: dict) -> None:
        """Publish message to Redis channel if configured."""
        if not manager.redis:
            return
        try:
            await manager.redis.publish(channel, json.dumps(message))
        except Exception:
            logging.exception("Failed to publish to redis")


async def _redis_listener(redis_client, channel_name: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    async for item in pubsub.listen():
        if item is None:
            continue
        if item['type'] == 'message':
            try:
                data = json.loads(item['data'])
                # Expect data to have 'target_user_id' and payload
                target = data.get('target_user_id')
                payload = data.get('payload')
                if target and payload:
                    await manager.send_json_to_user(str(target), payload)
            except Exception:
                logging.exception('Error processing pubsub message')


manager = ConnectionManager()
# Don't reference aioredis.Redis at import time (aioredis may be None)
manager.redis: Optional[Any] = None

# Initialize Redis if configured via settings
def init_redis():
    """Initialize Redis client if REDIS_URL is configured."""
    global manager
    if manager.redis is not None:
        # Already initialized
        return
    
    try:
        from app.config import get_settings
        settings = get_settings()
        redis_url = settings.redis_url
        if redis_url and aioredis is not None:
            try:
                manager.redis = aioredis.from_url(redis_url)
                # start background listener
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                # subscribe to dm events channel
                loop.create_task(_redis_listener(manager.redis, 'dm:events'))
                logging.info(f"Redis initialized: {redis_url}")
            except Exception as e:
                logging.exception(f'Failed to initialize Redis client: {e}')
                manager.redis = None
        else:
            if not redis_url:
                logging.info("REDIS_URL not configured, running without Redis pub/sub")
    except Exception as e:
        logging.exception(f'Error loading Redis settings: {e}')

