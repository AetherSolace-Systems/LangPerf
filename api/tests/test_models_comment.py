from app.models import (
    Comment,
    CommentMention,
    Organization,
    Trajectory,
    User,
)


async def test_comment_on_trajectory_node(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    session.add(u)
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.flush()

    c = Comment(
        org_id=org.id,
        trajectory_id=t.id,
        span_id="span-1",
        author_id=u.id,
        body="first comment",
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.id is not None
    assert c.resolved is False


async def test_mention_points_to_user(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    author = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    mentioned = User(org_id=org.id, email="c@d.co", password_hash="x", display_name="C")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([author, mentioned, t])
    await session.flush()
    c = Comment(org_id=org.id, trajectory_id=t.id, span_id="s", author_id=author.id, body="hi @C")
    session.add(c)
    await session.flush()
    m = CommentMention(comment_id=c.id, user_id=mentioned.id)
    session.add(m)
    await session.commit()
    assert m.comment_id == c.id
    assert m.user_id == mentioned.id
