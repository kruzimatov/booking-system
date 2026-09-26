"""Every model imported in one place, so Alembic and relationship lookups see all tables."""

from app.core.base import Base
from app.modules.users.models import User

__all__ = ["Base", "User"]
