"""A simple per-client upload limit stored in Redis (fixed one-minute windows)."""

import logging
import time

import redis
from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return one shared Redis connection (tests replace this dependency)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=2)
    return _redis_client


def enforce_upload_rate_limit(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis_client),
) -> None:
    """Raise a 429 error if this client has uploaded too many files this minute."""
    settings = get_settings()
    client_address = "unknown"
    if request.client is not None:
        client_address = request.client.host

    current_minute = int(time.time() // 60)
    counter_key = f"upload-limit:{client_address}:{current_minute}"

    try:
        upload_count = redis_client.incr(counter_key)
        if upload_count == 1:
            redis_client.expire(counter_key, 60)
    except redis.RedisError:
        # If Redis is down we let the upload through rather than block every user.
        logger.warning("Rate limiter unavailable, allowing request")
        return

    if upload_count > settings.uploads_per_minute_limit:
        raise AppError(429, "rate_limited", "Too many uploads. Please wait a minute.")
