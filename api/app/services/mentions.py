import re
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

MENTION_RE = re.compile(r"@([A-Za-z0-9_.+-]+(?:@[A-Za-z0-9.-]+)?)")


async def resolve_mentions(db: AsyncSession, org_id: str, body: str) -> list[User]:
    raw = MENTION_RE.findall(body)
    if not raw:
        return []
    tokens = [t.strip() for t in raw]
    query = select(User).where(
        User.org_id == org_id,
        or_(User.display_name.in_(tokens), User.email.in_(tokens)),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


def dedupe(users: Iterable[User]) -> list[User]:
    seen: set[str] = set()
    out: list[User] = []
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        out.append(u)
    return out
