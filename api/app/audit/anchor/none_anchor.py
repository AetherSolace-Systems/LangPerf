"""Dev-only no-op anchor. Production profiles reject this at startup."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models import AuditRoot, ExternalAnchor


class NoneAnchor(ExternalAnchorBackend):
    anchor_type = "none"

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=b"",
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=None,
        )
        session.add(row)
        await session.flush()
        return row
