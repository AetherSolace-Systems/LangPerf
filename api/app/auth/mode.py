import os
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


@dataclass(frozen=True)
class SyntheticUser:
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool


DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_SINGLE_USER = SyntheticUser(
    id=DEFAULT_USER_ID,
    org_id=DEFAULT_ORG_ID,
    email="single-user@localhost",
    display_name="Single User",
    is_admin=True,
)


async def is_single_user_mode(db: AsyncSession) -> bool:
    if os.environ.get("LANGPERF_SINGLE_USER") == "1":
        return True
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar_one()
    return count == 0
