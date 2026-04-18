from app.models import Organization


async def test_organization_can_be_created(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.commit()
    await session.refresh(org)
    assert org.id is not None
    assert org.name == "default"
    assert org.slug == "default"
    assert org.created_at is not None
