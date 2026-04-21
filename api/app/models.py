"""ORM models: Organization, User, Session, Agent, AgentVersion, Trajectory, Span, WorkspaceSetting.

Large payloads land in JSONB `attributes` on spans — Postgres TOASTs values
>2KB automatically so trajectories with long context windows compress in place.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Dialect-agnostic variants: use Postgres-native types on Postgres,
# fall back to portable types on other dialects (e.g. sqlite in tests).
JsonB = JSON().with_variant(JSONB(), "postgresql")
UUIDStr = String(36).with_variant(UUID(as_uuid=False), "postgresql")
# SQLite only auto-increments INTEGER PKs, not BIGINT. Use INTEGER on sqlite,
# BIGINT on Postgres so the audit tables work in both test lanes.
BigIntPK = Integer().with_variant(BigInteger(), "postgresql")


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_users_org_email"),)


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDStr, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_projects_org_slug"),)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    signature: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_prefix: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True, index=True)
    last_token_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUIDStr,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[str] = mapped_column(
        UUIDStr,
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="AgentVersion.first_seen_at.desc()",
    )
    project: Mapped["Project"] = relationship(lazy="selectin")


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    git_sha: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    short_sha: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    package_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint(
            "agent_id", "git_sha", "package_version", name="uq_agent_version_identity"
        ),
    )


class Trajectory(Base):
    __tablename__ = "trajectories"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    environment: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_tag: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # New in Phase 2a — populated by ingest; nullable so legacy rows exist until backfill runs.
    agent_id: Mapped[Optional[str]] = mapped_column(
        UUIDStr,
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_version_id: Mapped[Optional[str]] = mapped_column(
        UUIDStr,
        ForeignKey("agent_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_user_id: Mapped[str | None] = mapped_column(
        UUIDStr, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    spans: Mapped[list["Span"]] = relationship(
        back_populates="trajectory",
        cascade="all, delete-orphan",
        order_by="Span.started_at",
    )
    agent: Mapped[Optional["Agent"]] = relationship("Agent", foreign_keys=[agent_id])
    agent_version: Mapped[Optional["AgentVersion"]] = relationship(
        "AgentVersion", foreign_keys=[agent_version_id]
    )


class WorkspaceSetting(Base):
    __tablename__ = "workspace_settings"

    org_id: Mapped[str] = mapped_column(
        UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Span(Base):
    __tablename__ = "spans"

    span_id: Mapped[str] = mapped_column(String, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(
        UUIDStr,
        ForeignKey("trajectories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False)
    events: Mapped[Optional[list[Any]]] = mapped_column(JsonB, nullable=True)
    status_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trajectory: Mapped["Trajectory"] = relationship(back_populates="spans")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True)
    span_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    author_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_comment_id: Mapped[str | None] = mapped_column(UUIDStr, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class CommentMention(Base):
    __tablename__ = "comment_mentions"

    comment_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SharedLink(Base):
    __tablename__ = "shared_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FailureMode(Base):
    __tablename__ = "failure_modes"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="steel-mist")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_failure_modes_org_slug"),)


class TrajectoryFailureMode(Base):
    __tablename__ = "trajectory_failure_modes"

    trajectory_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("trajectories.id", ondelete="CASCADE"), primary_key=True)
    failure_mode_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("failure_modes.id", ondelete="CASCADE"), primary_key=True)
    tagged_by: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HeuristicHit(Base):
    __tablename__ = "heuristic_hits"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True)
    heuristic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    signature: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Rewrite(Base):
    __tablename__ = "rewrites"

    id: Mapped[str] = mapped_column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_span_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(UUIDStr, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    proposed_steps: Mapped[list[dict]] = mapped_column(JsonB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class AuditEntry(Base):
    """Append-only chain of audit events. Each row covers one event_type event.

    seq is the monotone counter that establishes chain order; prev_hash chains
    entries cryptographically so any gap or mutation is detectable.
    ingest_node_id uses UUIDStr (String/UUID variant) to stay sqlite-compatible;
    the Postgres migration uses PgUUID on the wire, but the ORM layer stays
    dialect-agnostic like every other model here.
    """

    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    prev_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    event_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    entry_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    # Optional attribution — present when an agent or human principal is known.
    agent_id: Mapped[Optional[str]] = mapped_column(UUIDStr, nullable=True)
    principal_human_id: Mapped[Optional[str]] = mapped_column(UUIDStr, nullable=True)
    agent_signature: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    ingest_node_id: Mapped[str] = mapped_column(UUIDStr, nullable=False)
    ingest_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_audit_entries_event_type_ts", "event_type", "ts"),
        Index("ix_audit_entries_agent_id_ts", "agent_id", "ts"),
        Index("ix_audit_entries_principal_human_id_ts", "principal_human_id", "ts"),
    )


class AuditRoot(Base):
    """Merkle tree root checkpoints computed over a range of audit_entries.

    tree_size is unique so each checkpoint covers a distinct prefix of the chain.
    """

    __tablename__ = "audit_roots"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    tree_size: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    root_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingest_node_id: Mapped[str] = mapped_column(UUIDStr, nullable=False)
    ingest_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    anchors: Mapped[list["ExternalAnchor"]] = relationship(
        back_populates="root", cascade="all, delete-orphan"
    )


class ExternalAnchor(Base):
    """Record of an audit root published to an external transparency log.

    anchor_type identifies the log (e.g. "none", "tlog"); anchor_ref is the
    opaque reference returned by the log (e.g. a checkpoint URL or leaf hash).
    """

    __tablename__ = "external_anchors"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    root_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("audit_roots.id"), nullable=False
    )
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anchor_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    root: Mapped["AuditRoot"] = relationship(back_populates="anchors")

    __table_args__ = (Index("ix_external_anchors_root_id", "root_id"),)
