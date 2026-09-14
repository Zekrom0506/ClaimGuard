"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api import health
from app.core.config import get_settings
from app.core.logging_config import configure_logging


def create_app() -> FastAPI:
    """Build the FastAPI app and register all routers."""
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        description="Decision support for prior-authorization checks. "
        "A human reviewer makes the final decision.",
    )
    application.include_router(health.router)

    @application.get("/")
    def root() -> dict[str, str]:
        """Simple hello-world route."""
        return {"message": "ClaimGuard API is running"}

    return application


app = create_app()
