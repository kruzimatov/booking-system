import enum

from sqlalchemy import Enum, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base, TimestampMixin, UUIDPrimaryKey


class UserRole(enum.StrEnum):
    CLIENT = "client"
    ADMIN = "admin"


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        default=UserRole.CLIENT,
        server_default=UserRole.CLIENT.value,
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
