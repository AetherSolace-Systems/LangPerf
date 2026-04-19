"""Deployment-mode helpers.

`is_single_user_mode` returns True when no users exist yet — the UI uses
this to show a "create first admin" bootstrap form. Once any user exists
it flips to "multi_user" and the login form takes over. There is no
synthetic auto-login — every request requires a real admin session.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def is_single_user_mode(db: AsyncSession) -> bool:
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar_one()
    return count == 0
