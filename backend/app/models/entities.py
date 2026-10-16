"""Business rows. Composite foreign keys prevent cross-organization relationships."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def utcnow():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Row:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Scoped(Row):
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)


def scoped(*constraints):
    return (UniqueConstraint("org_id", "id"), *constraints)


def request_fk():
    return ForeignKeyConstraint(
        ["org_id", "request_id"], ["maintenance_requests.org_id", "maintenance_requests.id"]
    )


class Organization(Row, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(150))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Karachi")


class User(Row, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)


class Membership(Scoped, Base):
    __tablename__ = "memberships"
    __table_args__ = scoped(
        UniqueConstraint("org_id", "user_id"), CheckConstraint("role IN ('ADMIN','STAFF','TENANT')")
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuthSession(Scoped, Base):
    __tablename__ = "sessions"
    __table_args__ = scoped(
        ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"])
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class LoginAttempt(Row, Base):
    __tablename__ = "login_attempts"
    key_hash: Mapped[str] = mapped_column(String(64), index=True)


class Property(Scoped, Base):
    __tablename__ = "properties"
    __table_args__ = scoped(UniqueConstraint("org_id", "name"))
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str] = mapped_column(String(300))


class Unit(Scoped, Base):
    __tablename__ = "units"
    __table_args__ = scoped(
        ForeignKeyConstraint(["org_id", "property_id"], ["properties.org_id", "properties.id"]),
        UniqueConstraint("property_id", "label"),
    )
    property_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(80))


class TenantUnitAssignment(Scoped, Base):
    __tablename__ = "tenant_unit_assignments"
    __table_args__ = scoped(
        ForeignKeyConstraint(["org_id", "unit_id"], ["units.org_id", "units.id"]),
        ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"]),
        UniqueConstraint("org_id", "user_id", "unit_id"),
    )
    unit_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36))


class MaintenanceRequest(Scoped, Base):
    __tablename__ = "maintenance_requests"
    __table_args__ = scoped(
        ForeignKeyConstraint(["org_id", "unit_id"], ["units.org_id", "units.id"]),
        ForeignKeyConstraint(
            ["org_id", "tenant_id"], ["memberships.org_id", "memberships.user_id"]
        ),
        CheckConstraint(
            "status IN ('PROCESSING','NEEDS_REVIEW','WAITING_FOR_TENANT','APPROVED','REJECTED','PROCESSING_FAILED')"
        ),
        Index("ix_requests_queue", "org_id", "status", "created_at"),
    )
    tenant_id: Mapped[str] = mapped_column(String(36))
    unit_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(150))
    original_message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PROCESSING")
    conversation_revision: Mapped[int] = mapped_column(Integer, default=1)
    draft_version: Mapped[int] = mapped_column(Integer, default=0)
    thread_id: Mapped[str] = mapped_column(String(160), unique=True)
    pending_command_id: Mapped[str | None] = mapped_column(String(36))
    processing_error: Mapped[str | None] = mapped_column(String(200))


class RequestMessage(Scoped, Base):
    __tablename__ = "request_messages"
    __table_args__ = scoped(request_fk(), UniqueConstraint("request_id", "revision"))
    request_id: Mapped[str] = mapped_column(String(36))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer)


class AIExtractionRevision(Scoped, Base):
    __tablename__ = "ai_extraction_revisions"
    __table_args__ = scoped(request_fk(), UniqueConstraint("job_id"))
    request_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[str] = mapped_column(String(36))
    source_revision: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(30))
    schema_version: Mapped[str] = mapped_column(String(30))


class ReviewedDraftRevision(Scoped, Base):
    __tablename__ = "reviewed_draft_revisions"
    __table_args__ = scoped(request_fk(), UniqueConstraint("request_id", "version"))
    request_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON)
    author_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(500))


class FieldCorrection(Scoped, Base):
    __tablename__ = "field_corrections"
    __table_args__ = scoped(request_fk())
    request_id: Mapped[str] = mapped_column(String(36))
    draft_version: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(60))
    previous_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(500))


class WorkflowCommand(Scoped, Base):
    __tablename__ = "workflow_commands"
    __table_args__ = scoped(request_fk(), UniqueConstraint("org_id", "operation_key"))
    request_id: Mapped[str] = mapped_column(String(36))
    operation_key: Mapped[str] = mapped_column(String(150))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    draft_version: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    result: Mapped[dict | None] = mapped_column(JSON)


class WorkOrder(Scoped, Base):
    __tablename__ = "work_orders"
    __table_args__ = scoped(
        request_fk(),
        UniqueConstraint("request_id"),
        CheckConstraint("status IN ('OPEN','IN_PROGRESS','COMPLETED','CANCELED')"),
    )
    request_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_draft_version: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[int] = mapped_column(Integer)


class DurableJob(Scoped, Base):
    __tablename__ = "durable_jobs"
    __table_args__ = scoped(
        request_fk(),
        UniqueConstraint("dedupe_key"),
        Index("ix_jobs_dispatch", "status", "lease_until"),
    )
    request_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(20))
    source_revision: Mapped[int] = mapped_column(Integer)
    command_id: Mapped[str | None] = mapped_column(String(36))
    dedupe_key: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(200))


class ModelInvocation(Scoped, Base):
    __tablename__ = "model_invocations"
    __table_args__ = scoped(request_fk())
    request_id: Mapped[str] = mapped_column(String(36))
    job_id: Mapped[str] = mapped_column(String(36))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(30))
    schema_version: Mapped[str] = mapped_column(String(30))
    source_revision: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(30))
    error_category: Mapped[str | None] = mapped_column(String(60))


class IdempotencyRecord(Scoped, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = scoped(UniqueConstraint("org_id", "user_id", "key"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(150))
    body_hash: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(ForeignKey("maintenance_requests.id"))


class Notification(Scoped, Base):
    __tablename__ = "notifications"
    __table_args__ = scoped(request_fk())
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    message: Mapped[str] = mapped_column(String(300))


class AuditEvent(Scoped, Base):
    __tablename__ = "audit_events"
    __table_args__ = scoped(Index("ix_audit_org_time", "org_id", "created_at"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
