"""Coverage for `GET /api/runs` (trajectory search + filtering)."""

from datetime import datetime, timedelta, timezone


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def _get_org(session):
    from app.models import Organization
    from sqlalchemy import select

    return (await session.execute(select(Organization))).scalar_one()


async def _get_project(session, org_id):
    from app.models import Project
    from sqlalchemy import select

    return (
        await session.execute(select(Project).where(Project.org_id == org_id))
    ).scalar_one()


async def test_list_runs_empty(client):
    await _bootstrap(client)
    r = await client.get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


async def test_list_runs_pagination(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    now = datetime.now(timezone.utc)
    # Seed 3 trajectories with distinct started_at so ordering is deterministic.
    for i in range(3):
        session.add(
            Trajectory(
                org_id=org.id,
                service_name="svc",
                name=f"r-{i}",
                started_at=now - timedelta(minutes=i),
            )
        )
    await session.commit()

    r = await client.get("/api/runs?limit=2&offset=1")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


async def test_list_runs_filter_by_tag(client, session):
    await _bootstrap(client)
    from app.models import Trajectory

    org = await _get_org(session)
    now = datetime.now(timezone.utc)
    session.add_all([
        Trajectory(org_id=org.id, service_name="svc", name="ok", started_at=now),
        Trajectory(org_id=org.id, service_name="svc", name="bad-1", status_tag="bad", started_at=now),
        Trajectory(org_id=org.id, service_name="svc", name="bad-2", status_tag="bad", started_at=now),
    ])
    await session.commit()

    r = await client.get("/api/runs?tag=bad")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(item["status_tag"] == "bad" for item in body["items"])

    # tag=none selects rows whose status_tag IS NULL.
    r_none = await client.get("/api/runs?tag=none")
    assert r_none.status_code == 200
    assert r_none.json()["total"] == 1


async def test_list_runs_filter_by_pattern(client, session):
    await _bootstrap(client)
    from app.models import Agent, Trajectory

    org = await _get_org(session)
    proj = await _get_project(session, org.id)
    a_weather = Agent(org_id=org.id, signature="sig-w", name="weather-bot", project_id=proj.id)
    a_triage = Agent(org_id=org.id, signature="sig-t", name="triage-agent", project_id=proj.id)
    session.add_all([a_weather, a_triage])
    await session.flush()
    now = datetime.now(timezone.utc)
    session.add_all([
        Trajectory(org_id=org.id, service_name="svc", agent_id=a_weather.id, environment="prod", started_at=now),
        Trajectory(org_id=org.id, service_name="svc", agent_id=a_triage.id, environment="dev", started_at=now),
    ])
    await session.commit()

    # Agent-slot glob: `weather-*` matches weather-bot only.
    r = await client.get("/api/runs?pattern=weather-*")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["agent_name"] == "weather-bot"

    # Env-slot glob: `*.prod.*` matches prod rows across agents.
    r_env = await client.get("/api/runs?pattern=*.prod.*")
    assert r_env.status_code == 200
    assert r_env.json()["total"] == 1
    assert r_env.json()["items"][0]["environment"] == "prod"


async def test_list_runs_filter_by_q(client, session):
    await _bootstrap(client)
    from app.models import Span, Trajectory

    org = await _get_org(session)
    now = datetime.now(timezone.utc)
    t_hit_name = Trajectory(org_id=org.id, service_name="svc", name="find-me-by-name", started_at=now)
    t_hit_span = Trajectory(org_id=org.id, service_name="svc", name="via-span", started_at=now)
    t_miss = Trajectory(org_id=org.id, service_name="svc", name="unrelated", started_at=now)
    session.add_all([t_hit_name, t_hit_span, t_miss])
    await session.flush()
    session.add(
        Span(
            span_id="sp1",
            trace_id="tr1",
            trajectory_id=t_hit_span.id,
            name="tool",
            kind="tool",
            started_at=now,
            attributes={"payload": "contains-needle-xyz"},
        )
    )
    await session.commit()

    r = await client.get("/api/runs?q=find-me-by-name")
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()["items"]}
    assert t_hit_name.id in ids
    assert t_miss.id not in ids

    # Matches via cast span.attributes → string substring search.
    r_span = await client.get("/api/runs?q=needle-xyz")
    assert r_span.status_code == 200
    ids_span = {item["id"] for item in r_span.json()["items"]}
    assert t_hit_span.id in ids_span
    assert t_miss.id not in ids_span


async def test_list_runs_limit_out_of_range_rejected(client):
    await _bootstrap(client)
    # limit has `ge=1, le=500` — values outside that range should 422.
    r = await client.get("/api/runs?limit=0")
    assert r.status_code == 422
    r2 = await client.get("/api/runs?limit=501")
    assert r2.status_code == 422
