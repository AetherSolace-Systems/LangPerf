from app.models import Organization, User
from app.services.mentions import resolve_mentions


async def test_resolve_mentions_matches_display_name_and_email(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    andrew = User(org_id=org.id, email="andrew@example.com", password_hash="x", display_name="Andrew")
    bea = User(org_id=org.id, email="bea@example.com", password_hash="x", display_name="Bea")
    session.add_all([andrew, bea]); await session.commit()

    users = await resolve_mentions(session, org.id, "hey @Andrew and @bea@example.com")
    ids = {u.id for u in users}
    assert andrew.id in ids
    assert bea.id in ids
