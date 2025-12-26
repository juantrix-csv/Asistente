from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, Text, Time, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from packages.db.database import Base


class MessageRaw(Base):
    __tablename__ = "messages_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False, default="whatsapp")
    chat_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    sender_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ConversationState(Base):
    __tablename__ = "conversation_state"

    chat_id: Mapped[str] = mapped_column(Text, primary_key=True)
    pending_action_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pending_question_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AutonomyRule(Base):
    __tablename__ = "autonomy_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    until_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Secret(Base):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ToolRun(Base):
    __tablename__ = "tool_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    output_json: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    decision_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    autonomy_mode_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProactiveEvent(Base):
    __tablename__ = "proactive_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False)
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False)
    strong_window_start: Mapped[time] = mapped_column(Time, nullable=False)
    strong_window_end: Mapped[time] = mapped_column(Time, nullable=False)
    daily_proactive_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    maybe_cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    urgent_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    maybe_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False)
    llm_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model_name: Mapped[str] = mapped_column(Text, nullable=False)
    llm_temperature: Mapped[float] = mapped_column(Float, nullable=False)
    llm_max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_json_mode: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    chat_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)


class AssistantNote(Base):
    __tablename__ = "assistant_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MemoryFact(Base):
    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssistantRequest(Base):
    __tablename__ = "assistant_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    asked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AssistantRequestEvent(Base):
    __tablename__ = "assistant_request_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
