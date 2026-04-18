async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_list_failure_modes_seeded(client):
    await _bootstrap(client)
    r = await client.get("/api/failure-modes")
    assert r.status_code == 200
    slugs = [m["slug"] for m in r.json()]
    assert "wrong_tool" in slugs
    assert "hallucination" in slugs


async def test_tag_and_untag_trajectory(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)

    modes = (await client.get("/api/failure-modes")).json()
    loop = next(m for m in modes if m["slug"] == "loop")
    r = await client.post(f"/api/trajectories/{t.id}/failure-modes", json={"failure_mode_id": loop["id"]})
    assert r.status_code == 200
    tagged = (await client.get(f"/api/trajectories/{t.id}/failure-modes")).json()
    assert any(m["slug"] == "loop" for m in tagged)
    r2 = await client.delete(f"/api/trajectories/{t.id}/failure-modes/{loop['id']}")
    assert r2.status_code == 204
