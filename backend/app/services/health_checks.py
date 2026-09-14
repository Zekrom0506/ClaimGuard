"""Checks used by the /ready endpoint to see if dependencies are reachable."""

import logging

import redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine

logger = logging.getLogger(__name__)


def is_database_reachable() -> bool:
    """Return True if PostgreSQL answers a trivial query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as error:
        logger.warning("Database check failed: %s", error)
        return False


def is_redis_reachable() -> bool:
    """Return True if Redis answers a PING."""
    try:
        redis_client = redis.Redis.from_url(get_settings().redis_url, socket_timeout=2)
        return bool(redis_client.ping())
    except Exception as error:
        logger.warning("Redis check failed: %s", error)
        return False
