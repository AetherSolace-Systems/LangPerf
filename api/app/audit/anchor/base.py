"""Abstract external-anchor interface.

A deployment may configure zero-or-more anchor types. Each ``anchor``
call persists one ``ExternalAnchor`` row bound to the given
``AuditRoot``. Anchor implementations never mutate other tables.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditRoot, ExternalAnchor


class ExternalAnchorBackend(ABC):
    """Base class for anchor backends."""

    anchor_type: str  # matches ExternalAnchor.anchor_type; one value per subclass

    @abstractmethod
    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        """Produce and persist an ExternalAnchor row for ``root``."""
        raise NotImplementedError
