"""Logging setup shared by the whole application."""

import logging


def configure_logging(log_level: str) -> None:
    """Send logs to the console in one consistent format."""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
