from app.models import Organization, User


async def test_user_belongs_to_org(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email="andrew@example.com",
        password_hash="fake-hash",
        display_name="Andrew",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.org_id == org.id
    assert user.is_admin is False
