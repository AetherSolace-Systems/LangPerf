"""RFC 3161 Time-Stamp Protocol anchor.

Builds a TimeStampReq (ASN.1 DER) containing the root hash, POSTs to the
configured TSA URL with ``Content-Type: application/timestamp-query``,
and stores the response body (TimeStampResp) as the anchor payload.
Interop with a real TSA is exercised in separate integration tests.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

import httpx
from asn1crypto import tsp
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models import AuditRoot, ExternalAnchor


class RFC3161Anchor(ExternalAnchorBackend):
    anchor_type = "rfc3161_tsa"

    def __init__(
        self,
        *,
        tsa_url: str,
        anchor_ref: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = tsa_url
        self._anchor_ref = anchor_ref
        self._http = http_client or httpx.AsyncClient()

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        req = tsp.TimeStampReq(
            {
                "version": "v1",
                "message_imprint": {
                    "hash_algorithm": {"algorithm": "sha256"},
                    "hashed_message": root.root_hash,
                },
                "nonce": int.from_bytes(secrets.token_bytes(8), "big"),
                "cert_req": True,
            }
        )
        resp = await self._http.post(
            self._url,
            content=req.dump(),
            headers={"Content-Type": "application/timestamp-query"},
        )
        resp.raise_for_status()

        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=resp.content,
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=self._anchor_ref,
        )
        session.add(row)
        await session.flush()
        return row
