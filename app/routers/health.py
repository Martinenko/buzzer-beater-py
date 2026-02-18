from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Any
from app.ws import manager
import asyncio

router = APIRouter()


@router.get("/redis")
async def redis_health() -> Any:
    """Return Redis connection health. If `REDIS_URL` is not configured, returns status `not_configured`.

    This endpoint is safe for quick verification after deploying the backend.
    """
    if not getattr(manager, "redis", None):
        return JSONResponse({"status": "not_configured", "details": "REDIS_URL not set or redis not installed"}, status_code=200)

    try:
        # aioredis ping returns True on success
        ok = await manager.redis.ping()
        if ok:
            return {"status": "ok", "redis": "connected"}
        else:
            return JSONResponse({"status": "error", "redis": "ping_failed"}, status_code=500)
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
