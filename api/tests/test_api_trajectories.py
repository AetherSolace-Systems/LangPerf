from datetime import datetime, timedelta, timezone


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def _get_org(session):
    from sqlalchemy import select

    from app.models import Organization

    return (await session.execute(select(Organization))).scalar_one()


async def test_list_trajectories_empty(client):
    await _bootstrap(client)
    r = await client.get("/api/trajectories")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_trajectories_pagination(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    base = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
    for i in range(3):
        session.add(
            Trajectory(
                org_id=org.id,
                trace_id=f"t{i}",
                service_name="svc",
                name=f"traj-{i}",
                started_at=base + timedelta(seconds=i),
            )
        )
    await session.commit()

    r = await client.get("/api/trajectories?limit=2&offset=1")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


async def test_list_trajectories_filter_by_tag(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    for name, tag in [("good-one", "good"), ("bad-one", "bad"), ("untagged", None)]:
        session.add(
            Trajectory(
                org_id=org.id, trace_id=name, service_name="svc", name=name, status_tag=tag
            )
        )
    await session.commit()

    r = await client.get("/api/trajectories?tag=good")
    assert r.status_code == 200
    body = r.json()
    names = {t["name"] for t in body["items"]}
    assert names == {"good-one"}

    r_none = await client.get("/api/trajectories?tag=none")
    assert r_none.status_code == 200
    assert {t["name"] for t in r_none.json()["items"]} == {"untagged"}


async def test_facets_returns_distinct_values(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    session.add_all(
        [
            Trajectory(
                org_id=org.id, trace_id="a", service_name="svc-a",
                environment="prod", status_tag="good", name="a",
            ),
            Trajectory(
                org_id=org.id, trace_id="b", service_name="svc-b",
                environment="dev", status_tag="bad", name="b",
            ),
            Trajectory(
                org_id=org.id, trace_id="c", service_name="svc-a",
                environment="prod", status_tag="good", name="c",
            ),
        ]
    )
    await session.commit()

    r = await client.get("/api/trajectories/facets")
    assert r.status_code == 200
    body = r.json()
    assert sorted(body["services"]) == ["svc-a", "svc-b"]
    assert sorted(body["environments"]) == ["dev", "prod"]
    assert sorted(body["tags"]) == ["bad", "good"]


async def test_get_trajectory_detail_includes_spans(client, session):
    await _bootstrap(client)
    from app.models import Span, Trajectory

    org = await _get_org(session)
    t = Trajectory(org_id=org.id, trace_id="tt", service_name="svc", name="n")
    session.add(t)
    await session.flush()
    base = datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc)
    session.add_all(
        [
            Span(
                span_id="s2", trace_id="tt", trajectory_id=t.id, name="second",
                kind="llm", started_at=base + timedelta(seconds=10), attributes={},
            ),
            Span(
                span_id="s1", trace_id="tt", trajectory_id=t.id, name="first",
                kind="tool", started_at=base, attributes={"tool.name": "x"},
            ),
        ]
    )
    await session.commit()

    r = await client.get(f"/api/trajectories/{t.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == t.id
    span_ids = [s["span_id"] for s in body["spans"]]
    # Trajectory.spans is ordered by Span.started_at
    assert span_ids == ["s1", "s2"]


async def test_get_trajectory_404_for_unknown(client):
    await _bootstrap(client)
    r = await client.get("/api/trajectories/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_patch_trajectory_updates_status_tag_and_notes(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    t = Trajectory(org_id=org.id, trace_id="p", service_name="svc", name="p")
    session.add(t)
    await session.commit()
    await session.refresh(t)

    r = await client.patch(
        f"/api/trajectories/{t.id}",
        json={"status_tag": "interesting", "notes": "look at this"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status_tag"] == "interesting"
    assert body["notes"] == "look at this"

    # Confirm persistence via GET
    got = await client.get(f"/api/trajectories/{t.id}")
    assert got.status_code == 200
    got_body = got.json()
    assert got_body["status_tag"] == "interesting"
    assert got_body["notes"] == "look at this"


async def test_patch_trajectory_rejects_invalid_tag(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    t = Trajectory(org_id=org.id, trace_id="x", service_name="svc", name="x")
    session.add(t)
    await session.commit()
    await session.refresh(t)

    r = await client.patch(f"/api/trajectories/{t.id}", json={"status_tag": "not-a-tag"})
    assert r.status_code == 400


async def test_trajectory_org_scoping_hides_other_org(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory

    other = Organization(name="other", slug="other")
    session.add(other)
    await session.flush()
    hidden = Trajectory(
        org_id=other.id, trace_id="hidden", service_name="svc", name="hidden"
    )
    session.add(hidden)
    await session.commit()
    await session.refresh(hidden)

    # Detail endpoint
    r = await client.get(f"/api/trajectories/{hidden.id}")
    assert r.status_code == 404
    # PATCH endpoint
    r_patch = await client.patch(
        f"/api/trajectories/{hidden.id}", json={"status_tag": "good"}
    )
    assert r_patch.status_code == 404
    # List endpoint
    r_list = await client.get("/api/trajectories")
    assert r_list.status_code == 200
    assert all(t["id"] != hidden.id for t in r_list.json()["items"])
