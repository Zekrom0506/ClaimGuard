"""Logging setup shared by the whole application.

Rule for the whole codebase: never log document text or patient details.
Log ids, statuses and timings only.
"""

import logging

from app.core.request_context import RequestIdLogFilter


def configure_logging(log_level: str) -> None:
    """Send logs to the console in one format that includes the request id."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdLogFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
