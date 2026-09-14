"""Health and readiness endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services import health_checks

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Say the API process is running. Does not check other services."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    """Say whether the API can serve traffic, i.e. its dependencies are up."""
    database_ok = health_checks.is_database_reachable()
    redis_ok = health_checks.is_redis_reachable()

    if database_ok and redis_ok:
        status_code = 200
    else:
        status_code = 503

    return JSONResponse(
        status_code=status_code,
        content={"database": database_ok, "redis": redis_ok},
    )
