from sqlalchemy import func, select

from app.core.errors import require
from app.models import MaintenanceRequest, RequestMessage, ReviewedDraftRevision, WorkOrder


def request_for(db, actor, request_id, lock=False):
    query = select(MaintenanceRequest).where(
        MaintenanceRequest.id == request_id, MaintenanceRequest.org_id == actor.org_id
    )
    if actor.role == "TENANT":
        query = query.where(MaintenanceRequest.tenant_id == actor.user_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    require(row is not None, "NOT_FOUND", "Request not found", 404)
    return row


def messages(db, req):
    return db.scalars(
        select(RequestMessage)
        .where(RequestMessage.request_id == req.id, RequestMessage.org_id == req.org_id)
        .order_by(RequestMessage.revision)
    ).all()


def draft(db, req):
    return db.scalar(
        select(ReviewedDraftRevision).where(
            ReviewedDraftRevision.request_id == req.id,
            ReviewedDraftRevision.version == req.draft_version,
        )
    )


def order_for(db, req):
    return db.scalar(
        select(WorkOrder).where(WorkOrder.request_id == req.id, WorkOrder.org_id == req.org_id)
    )


def page(db, query, number=1, size=25):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {
        "items": list(db.scalars(query.offset((number - 1) * size).limit(size)).all()),
        "total": total,
        "page": number,
        "page_size": size,
    }
