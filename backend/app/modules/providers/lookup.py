"""The one rule for finding a provider, shared by every service that needs one."""

import uuid

from app.core.errors import NotFoundError
from app.modules.providers.models import Provider
from app.modules.providers.repository import ProviderRepository


def find_provider(
    providers: ProviderRepository,
    provider_id: uuid.UUID,
    *,
    active_only: bool,
    lock: bool = False,
) -> Provider:
    """Missing, or inactive where an active one is required, is a 404.

    lock=True takes the provider row lock (SELECT ... FOR UPDATE) that serializes every
    change to this provider's schedule; see the lock order in docs/ARCHITECTURE.md.
    """
    provider = providers.lock(provider_id) if lock else providers.get(provider_id)
    if provider is None or (active_only and not provider.is_active):
        raise NotFoundError("Provider not found.")
    return provider
