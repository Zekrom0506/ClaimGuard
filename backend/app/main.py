"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import cases, health
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging_config import configure_logging
from app.core.request_context import RequestIdMiddleware
from app.services.pipeline import build_pipeline_dependencies


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create long-lived helpers once at startup instead of on every request."""
    application.state.pipeline = build_pipeline_dependencies(get_settings())
    yield


def create_app() -> FastAPI:
    """Build the FastAPI app and register all routers."""
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        description="Decision support for prior-authorization checks. "
        "A human reviewer makes the final decision.",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    register_error_handlers(application)

    application.include_router(health.router)
    application.include_router(cases.router)

    @application.get("/")
    def root() -> dict[str, str]:
        """Simple hello-world route."""
        return {"message": "ClaimGuard API is running"}

    return application


app = create_app()
