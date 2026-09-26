import uuid

from sqlalchemy import Column, ForeignKey, String, Table, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKey
from app.modules.catalog.models import Service

provider_service_links = Table(
    "provider_services",
    Base.metadata,
    Column("provider_id", ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "service_id", ForeignKey("services.id", ondelete="CASCADE"), primary_key=True, index=True
    ),
)


class Provider(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "providers"

    full_name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text)
    # Contact fields are admin-only; public schemas never include them.
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    services: Mapped[list[Service]] = relationship(
        secondary=provider_service_links, order_by=Service.name, lazy="selectin"
    )

    @property
    def service_ids(self) -> list[uuid.UUID]:
        return [service.id for service in self.services]

    @property
    def active_service_ids(self) -> list[uuid.UUID]:
        return [service.id for service in self.services if service.is_active]
