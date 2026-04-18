"""ORM models: Trajectory, Span, Agent, AgentVersion.

Large payloads land in JSONB `attributes` on spans — Postgres TOASTs values
>2KB automatically so trajectories with long context windows compress in place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
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

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="AgentVersion.first_seen_at.desc()",
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
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

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    environment: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
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
        UUID(as_uuid=False),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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


class Span(Base):
    __tablename__ = "spans"

    span_id: Mapped[str] = mapped_column(String, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
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
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    events: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trajectory: Mapped["Trajectory"] = relationship(back_populates="spans")
