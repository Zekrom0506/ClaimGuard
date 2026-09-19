"""One JSON shape for every error the API returns.

Every error looks like:
    {"error": {"code": "file_too_large", "message": "...", "request_id": "..."}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An expected error with an HTTP status, a short code and a readable message."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def build_error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Create the standard error body."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": current_request_id.get(),
            }
        },
    )


async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
    """Errors we raise on purpose."""
    return build_error_response(error.status_code, error.code, error.message)


async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    """Framework errors such as 404 for an unknown URL."""
    return build_error_response(error.status_code, "http_error", str(error.detail))


async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """Request bodies or parameters that do not match the expected shape."""
    problems = []
    for problem in error.errors():
        location = ".".join(str(part) for part in problem["loc"])
        problems.append(f"{location}: {problem['msg']}")
    return build_error_response(422, "validation_error", "; ".join(problems))


async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    """Anything else. Details go to the log, never to the client."""
    logger.exception("Unhandled error")
    return build_error_response(500, "internal_error", "Something went wrong.")


def register_error_handlers(application: FastAPI) -> None:
    """Connect the handlers above to the app."""
    application.add_exception_handler(AppError, handle_app_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_error)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(Exception, handle_unexpected_error)
