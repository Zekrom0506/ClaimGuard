"""Import every table here so Alembic and create_all can see them."""

from app.models.case import CaseStatus, PriorAuthCase

__all__ = ["CaseStatus", "PriorAuthCase"]
