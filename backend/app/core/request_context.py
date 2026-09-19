"""Request ids: one id per HTTP request, attached to every log line and error."""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

# A ContextVar keeps a separate value for each request, even when many
# requests are handled at the same time.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Give every request an id (or reuse the caller's) and return it in a header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Set the id for this request, call the route, then add the response header."""
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = current_request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            current_request_id.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RequestIdLogFilter(logging.Filter):
    """Adds the current request id to every log record as `request_id`."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the id; always keep the record."""
        record.request_id = current_request_id.get()
        return True
