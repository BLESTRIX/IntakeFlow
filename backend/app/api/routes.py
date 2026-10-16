import secrets

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import actor, csrf_guard
from app.core.config import get_settings
from app.core.errors import DomainError, require
from app.db.session import get_db
from app.models import (
    AIExtractionRevision,
    AuditEvent,
    AuthSession,
    FieldCorrection,
    MaintenanceRequest,
    Membership,
    ModelInvocation,
    Notification,
    Property,
    ReviewedDraftRevision,
    TenantUnitAssignment,
    Unit,
    User,
    WorkflowCommand,
    WorkOrder,
)
from app.repositories import queries
from app.schemas.api import (
    AssignmentIn,
    DraftPatch,
    LoginIn,
    MemberIn,
    MembershipPatch,
    MessageIn,
    PropertyIn,
    RegisterIn,
    RequestIn,
    RequestStatus,
    ReviewAction,
    UnitIn,
    WorkOrderPatch,
)
from app.services import auth, intake, management
from app.services.states import completeness

router = APIRouter(prefix="/api/v1", dependencies=[Depends(csrf_guard)])
DB = Depends(get_db)
WHO = Depends(actor)


def row_dict(row, exclude=()):
    return {
        c.name: getattr(row, c.name)
        for c in row.__table__.columns
        if c.name not in {"org_id", "thread_id", *exclude}
    }


def cookie_options():
    return {"secure": get_settings().secure_cookies, "samesite": "lax", "path": "/"}


def set_session(response, tokens):
    token, csrf = tokens
    age = get_settings().session_hours * 3600
    response.set_cookie("intakeflow_session", token, httponly=True, max_age=age, **cookie_options())
    response.set_cookie("intakeflow_csrf", csrf, httponly=False, max_age=age, **cookie_options())
    return {"message": "Signed in", "csrf_token": csrf}


@router.get("/auth/csrf", tags=["Authentication"])
def csrf(request: Request, response: Response, db: Session = DB):
    token = secrets.token_urlsafe(32)
    if request.cookies.get("intakeflow_session"):
        try:
            who = auth.authenticate(db, request.cookies["intakeflow_session"])
        except DomainError:
            response.delete_cookie("intakeflow_session", path="/")
        else:
            session = db.get(AuthSession, who.session_id)
            existing = request.cookies.get("intakeflow_csrf", "")
            if existing and secrets.compare_digest(session.csrf_hash, auth.digest(existing)):
                token = existing
            else:
                session.csrf_hash = auth.digest(token)
                db.commit()
    response.set_cookie("intakeflow_csrf", token, httponly=False, max_age=86400, **cookie_options())
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.post("/auth/register", tags=["Authentication"], status_code=201)
def register(data: RegisterIn, request: Request, response: Response, db: Session = DB):
    auth.rate_limit(db, f"register:{request.client.host}")
    return set_session(response, auth.register(db, data))


@router.post("/auth/login", tags=["Authentication"])
def login(data: LoginIn, request: Request, response: Response, db: Session = DB):
    return set_session(response, auth.login(db, data, request.client.host))


@router.post("/auth/logout", tags=["Authentication"])
def logout(response: Response, db: Session = DB, who=WHO):
    db.delete(db.get(AuthSession, who.session_id))
    db.commit()
    response.delete_cookie("intakeflow_session", path="/")
    response.delete_cookie("intakeflow_csrf", path="/")
    return {"message": "Signed out"}


@router.get("/auth/me", tags=["Authentication"])
def me(db: Session = DB, who=WHO):
    return auth.profile(db, who)


@router.get("/properties", tags=["Properties"])
def properties(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    query = select(Property).where(Property.org_id == who.org_id)
    if who.role == "TENANT":
        assigned = (
            select(Unit.property_id)
            .join(TenantUnitAssignment, TenantUnitAssignment.unit_id == Unit.id)
            .where(
                TenantUnitAssignment.org_id == who.org_id,
                TenantUnitAssignment.user_id == who.user_id,
            )
        )
        query = query.where(Property.id.in_(assigned))
    return queries.page(db, query.order_by(Property.name), page, page_size)


@router.post("/properties", tags=["Properties"], status_code=201)
def add_property(data: PropertyIn, db: Session = DB, who=WHO):
    """ADMIN only; creates a property in the authenticated organization."""
    return management.create_property(db, who, data)


@router.post("/properties/{property_id}/units", tags=["Properties"], status_code=201)
def add_unit(property_id: str, data: UnitIn, db: Session = DB, who=WHO):
    return management.create_unit(db, who, property_id, data)


@router.get("/units", tags=["Properties"])
def units(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    query = select(Unit).where(Unit.org_id == who.org_id)
    if who.role == "TENANT":
        query = query.where(
            Unit.id.in_(
                select(TenantUnitAssignment.unit_id).where(
                    TenantUnitAssignment.org_id == who.org_id,
                    TenantUnitAssignment.user_id == who.user_id,
                )
            )
        )
    result = queries.page(db, query.order_by(Unit.label), page, page_size)
    result["items"] = [
        {**row_dict(u), "property_name": db.get(Property, u.property_id).name}
        for u in result["items"]
    ]
    return result


@router.get("/memberships", tags=["Administration"])
def members(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    auth.admin(who)
    result = queries.page(
        db,
        select(Membership).where(Membership.org_id == who.org_id).order_by(Membership.created_at),
        page,
        page_size,
    )
    result["items"] = [
        {
            **row_dict(m),
            "name": db.get(User, m.user_id).name,
            "email": db.get(User, m.user_id).email,
        }
        for m in result["items"]
    ]
    return result


@router.post("/memberships", tags=["Administration"], status_code=201)
def add_member(data: MemberIn, db: Session = DB, who=WHO):
    return management.create_member(db, who, data)


@router.get("/assignments", tags=["Administration"])
def assignments(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    auth.admin(who)
    return queries.page(
        db,
        select(TenantUnitAssignment)
        .where(TenantUnitAssignment.org_id == who.org_id)
        .order_by(TenantUnitAssignment.created_at),
        page,
        page_size,
    )


@router.post("/assignments", tags=["Administration"], status_code=201)
def add_assignment(data: AssignmentIn, db: Session = DB, who=WHO):
    return management.assign_unit(db, who, data)


@router.patch("/properties/{property_id}", tags=["Properties"])
def patch_property(property_id: str, data: PropertyIn, db: Session = DB, who=WHO):
    return management.edit_property(db, who, property_id, data)


@router.patch("/units/{unit_id}", tags=["Properties"])
def patch_unit(unit_id: str, data: UnitIn, db: Session = DB, who=WHO):
    return management.edit_unit(db, who, unit_id, data)


@router.patch("/memberships/{membership_id}", tags=["Administration"])
def patch_membership(membership_id: str, data: MembershipPatch, db: Session = DB, who=WHO):
    return management.edit_membership(db, who, membership_id, data)


@router.delete("/assignments/{assignment_id}", tags=["Administration"])
def delete_assignment(assignment_id: str, db: Session = DB, who=WHO):
    return management.remove_assignment(db, who, assignment_id)


def request_summary(db, req):
    unit = db.get(Unit, req.unit_id)
    return {
        **row_dict(req, exclude=("original_message",)),
        "unit_label": unit.label,
        "property_name": db.get(Property, unit.property_id).name,
    }


@router.post("/requests", tags=["Requests"], status_code=201)
def create_request(
    data: RequestIn,
    idempotency_key: str = Header(..., min_length=1, max_length=150),
    db: Session = DB,
    who=WHO,
):
    """TENANT only, assigned units only. Same Idempotency-Key + body replays the original; changed body returns 409. No similarity merging."""
    return request_summary(db, intake.submit(db, who, data, idempotency_key))


@router.get("/requests", tags=["Requests"])
def requests(
    db: Session = DB,
    who=WHO,
    status: RequestStatus | None = None,
    q: str = Query("", max_length=150),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    query = select(MaintenanceRequest).where(MaintenanceRequest.org_id == who.org_id)
    if who.role == "TENANT":
        query = query.where(MaintenanceRequest.tenant_id == who.user_id)
    if status:
        query = query.where(MaintenanceRequest.status == status)
    if q:
        query = query.where(MaintenanceRequest.title.ilike(f"%{q}%"))
    result = queries.page(db, query.order_by(MaintenanceRequest.created_at.desc()), page, page_size)
    result["items"] = [request_summary(db, r) for r in result["items"]]
    return result


@router.get("/requests/{request_id}", tags=["Requests"])
def request_detail(request_id: str, db: Session = DB, who=WHO):
    req = queries.request_for(db, who, request_id)
    result = request_summary(db, req)
    result["messages"] = [row_dict(m) for m in queries.messages(db, req)]
    order = queries.order_for(db, req)
    result["work_order"] = row_dict(order) if order else None
    if who.role != "TENANT":
        current = queries.draft(db, req)
        result["draft"] = row_dict(current)
        result["approval_missing"] = completeness(current.data)
        result["draft_stale"] = current.source_revision != req.conversation_revision
        command = (
            db.get(WorkflowCommand, req.pending_command_id) if req.pending_command_id else None
        )
        result["pending_command"] = row_dict(command) if command else None
    return result


@router.post("/requests/{request_id}/messages", tags=["Requests"])
def message(request_id: str, data: MessageIn, db: Session = DB, who=WHO):
    return request_summary(db, intake.add_message(db, who, request_id, data.body))


@router.get("/requests/{request_id}/extractions", tags=["Review"])
def extractions(
    request_id: str,
    db: Session = DB,
    who=WHO,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    auth.staff(who)
    req = queries.request_for(db, who, request_id)
    return queries.page(
        db,
        select(AIExtractionRevision)
        .where(AIExtractionRevision.request_id == req.id)
        .order_by(AIExtractionRevision.created_at.desc()),
        page,
        page_size,
    )


@router.get("/requests/{request_id}/draft", tags=["Review"])
def get_draft(request_id: str, db: Session = DB, who=WHO):
    auth.staff(who)
    req = queries.request_for(db, who, request_id)
    return {
        "current": queries.draft(db, req),
        "history": db.scalars(
            select(ReviewedDraftRevision)
            .where(ReviewedDraftRevision.request_id == req.id)
            .order_by(ReviewedDraftRevision.version.desc())
        ).all(),
        "corrections": db.scalars(
            select(FieldCorrection)
            .where(FieldCorrection.request_id == req.id)
            .order_by(FieldCorrection.created_at.desc())
        ).all(),
    }


@router.patch("/requests/{request_id}/draft", tags=["Review"])
def patch_draft(request_id: str, data: DraftPatch, db: Session = DB, who=WHO):
    """Staff only; expected_version and source_revision protect against lost updates. Routing team is derived from the reviewed category."""
    return intake.edit_draft(db, who, request_id, data)


@router.post("/requests/{request_id}/request-clarification", tags=["Review"], status_code=202)
def clarify(
    request_id: str,
    data: ReviewAction,
    idempotency_key: str = Header(...),
    db: Session = DB,
    who=WHO,
):
    """Queues an authorized, version-bound command. AI questions are never sent automatically."""
    return intake.queue_action(db, who, request_id, "clarify", data, idempotency_key)


@router.post("/requests/{request_id}/approve", tags=["Review"], status_code=202)
def approve(
    request_id: str,
    data: ReviewAction,
    idempotency_key: str = Header(...),
    db: Session = DB,
    who=WHO,
):
    """Staff only. Queues approval against current conversation and complete draft. Worker atomically creates exactly one work order; 202 is pending, not approval."""
    return intake.queue_action(db, who, request_id, "approve", data, idempotency_key)


@router.post("/requests/{request_id}/reject", tags=["Review"], status_code=202)
def reject(
    request_id: str,
    data: ReviewAction,
    idempotency_key: str = Header(...),
    db: Session = DB,
    who=WHO,
):
    return intake.queue_action(db, who, request_id, "reject", data, idempotency_key)


@router.post("/requests/{request_id}/retry-processing", tags=["Review"])
def retry(request_id: str, db: Session = DB, who=WHO):
    return intake.retry(db, who, request_id)


@router.get("/work-orders", tags=["Work orders"])
def orders(
    db: Session = DB,
    who=WHO,
    status: str | None = Query(None, pattern="^(OPEN|IN_PROGRESS|COMPLETED|CANCELED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    query = select(WorkOrder).where(WorkOrder.org_id == who.org_id)
    if who.role == "TENANT":
        query = query.where(
            WorkOrder.request_id.in_(
                select(MaintenanceRequest.id).where(
                    MaintenanceRequest.tenant_id == who.user_id,
                    MaintenanceRequest.org_id == who.org_id,
                )
            )
        )
    if status:
        query = query.where(WorkOrder.status == status)
    return queries.page(db, query.order_by(WorkOrder.created_at.desc()), page, page_size)


@router.get("/work-orders/{order_id}", tags=["Work orders"])
def order_detail(order_id: str, db: Session = DB, who=WHO):
    row = db.scalar(
        select(WorkOrder).where(WorkOrder.org_id == who.org_id, WorkOrder.id == order_id)
    )
    require(row is not None, "NOT_FOUND", "Work order not found", 404)
    req = queries.request_for(db, who, row.request_id)
    return {**row_dict(row), "request": request_summary(db, req)}


@router.patch("/work-orders/{order_id}", tags=["Work orders"])
def patch_order(order_id: str, data: WorkOrderPatch, db: Session = DB, who=WHO):
    return intake.update_order(db, who, order_id, data)


@router.get("/notifications", tags=["Operations"])
def notifications(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    return queries.page(
        db,
        select(Notification)
        .where(Notification.org_id == who.org_id, Notification.user_id == who.user_id)
        .order_by(Notification.created_at.desc()),
        page,
        page_size,
    )


@router.get("/dashboard", tags=["Operations"])
def dashboard(db: Session = DB, who=WHO):
    query = select(MaintenanceRequest.status, func.count()).where(
        MaintenanceRequest.org_id == who.org_id
    )
    if who.role == "TENANT":
        query = query.where(MaintenanceRequest.tenant_id == who.user_id)
    counts = dict(db.execute(query.group_by(MaintenanceRequest.status)).all())
    return {
        "counts": counts,
        "total": sum(counts.values()),
        "ai_provider": get_settings().ai_provider,
    }


@router.get("/ai-usage", tags=["Administration"])
def usage(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    auth.admin(who)
    return queries.page(
        db,
        select(ModelInvocation)
        .where(ModelInvocation.org_id == who.org_id)
        .order_by(ModelInvocation.created_at.desc()),
        page,
        page_size,
    )


@router.get("/audit-events", tags=["Administration"])
def events(
    db: Session = DB, who=WHO, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    auth.admin(who)
    return queries.page(
        db,
        select(AuditEvent)
        .where(AuditEvent.org_id == who.org_id)
        .order_by(AuditEvent.created_at.desc()),
        page,
        page_size,
    )


@router.get("/health/live", tags=["Health"])
def live():
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
def ready(db: Session = DB):
    from redis import Redis

    from app.tasks.worker import celery

    db.execute(text("SELECT 1 FROM alembic_version"))
    db.execute(text("SELECT 1 FROM checkpoint_migrations LIMIT 1"))
    require(
        Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, socket_timeout=2).ping(),
        "NOT_READY",
        "Broker is unavailable",
        503,
    )
    return {"status": "ready", "database": "ok", "broker": "ok", "task_app": celery.main}
