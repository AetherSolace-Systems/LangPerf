async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_create_shared_link(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)
    r = await client.post(f"/api/trajectories/{t.id}/share", json={})
    assert r.status_code == 201
    assert r.json()["token"]


async def test_resolve_shared_link_for_authed_user_same_org(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)
    created = await client.post(f"/api/trajectories/{t.id}/share", json={})
    token = created.json()["token"]
    r = await client.get(f"/api/shared/{token}")
    assert r.status_code == 200
    assert r.json()["trajectory_id"] == t.id


async def test_resolve_revoked_link_is_404(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)
    created = await client.post(f"/api/trajectories/{t.id}/share", json={})
    token = created.json()["token"]
    await client.post(f"/api/shared/{token}/revoke")
    r = await client.get(f"/api/shared/{token}")
    assert r.status_code == 404
