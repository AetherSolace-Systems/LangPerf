async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def _seed_trajectory(session):
    from sqlalchemy import select
    from app.models import Organization, Trajectory
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)
    return t


async def test_create_rewrite(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    r = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={
            "branch_span_id": "span-4",
            "rationale": "wrong tool",
            "proposed_steps": [
                {"kind": "tool_call", "tool_name": "search_invoices", "arguments": {"q": "x"}},
                {"kind": "final_answer", "text": "here"},
            ],
            "status": "draft",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["branch_span_id"] == "span-4"
    assert len(r.json()["proposed_steps"]) == 2


async def test_list_rewrites(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    r = await client.get(f"/api/trajectories/{t.id}/rewrites")
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_update_rewrite_by_author(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    created = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    rid = created.json()["id"]
    r = await client.patch(
        f"/api/rewrites/{rid}",
        json={"rationale": "updated", "proposed_steps": [{"kind": "final_answer", "text": "ok"}], "status": "submitted"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"


async def test_delete_rewrite(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    created = await client.post(
        f"/api/trajectories/{t.id}/rewrites",
        json={"branch_span_id": "s1", "rationale": "", "proposed_steps": [], "status": "draft"},
    )
    rid = created.json()["id"]
    r = await client.delete(f"/api/rewrites/{rid}")
    assert r.status_code == 204
