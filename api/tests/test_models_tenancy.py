import uuid as _uuid

from app.models import Agent, Organization, Project, Trajectory, WorkspaceSetting


async def test_agent_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    proj = Project(id=str(_uuid.uuid4()), org_id=org.id, name="Default", slug="default")
    session.add(proj); await session.flush()
    a = Agent(org_id=org.id, signature="sig", name="n", display_name="N", project_id=proj.id)
    session.add(a)
    await session.commit()
    assert a.org_id == org.id


async def test_trajectory_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="tid", service_name="svc", name="n")
    session.add(t)
    await session.commit()
    assert t.org_id == org.id


async def test_workspace_setting_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    ws = WorkspaceSetting(org_id=org.id, key="k", value={"a": 1})
    session.add(ws)
    await session.commit()
    assert ws.org_id == org.id
