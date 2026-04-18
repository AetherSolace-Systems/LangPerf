from app.models import Organization, Rewrite, Trajectory, User


async def test_rewrite_with_proposed_steps(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()

    r = Rewrite(
        org_id=org.id,
        trajectory_id=t.id,
        branch_span_id="span-4",
        author_id=u.id,
        rationale="wrong tool — should have searched invoices not orders",
        proposed_steps=[
            {"kind": "tool_call", "tool_name": "search_invoices", "arguments": {"q": "last month"}},
            {"kind": "final_answer", "text": "You had 3 invoices last month totaling $4,500."},
        ],
        status="draft",
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    assert r.id is not None
    assert len(r.proposed_steps) == 2
