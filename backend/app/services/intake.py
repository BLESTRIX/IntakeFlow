import json

from sqlalchemy import select, text

from app.core.errors import require
from app.models import (
    AIExtractionRevision,
    AuditEvent,
    DurableJob,
    FieldCorrection,
    IdempotencyRecord,
    MaintenanceRequest,
    Notification,
    RequestMessage,
    ReviewedDraftRevision,
    TenantUnitAssignment,
    Unit,
    WorkflowCommand,
    WorkOrder,
    uid,
)
from app.repositories import queries
from app.schemas.api import ReviewedValues
from app.services.auth import digest, staff, tenant
from app.services.states import ORDER_TRANSITIONS, TEAMS, completeness, transition


def audit(db, actor, entity_id, action, details=None):
    db.add(
        AuditEvent(
            org_id=actor.org_id,
            actor_id=actor.user_id,
            entity_id=entity_id,
            action=action,
            details=details or {},
        )
    )


def notify(db, req, message):
    db.add(
        Notification(org_id=req.org_id, user_id=req.tenant_id, request_id=req.id, message=message)
    )


def schedule_extraction(db, req, suffix=""):
    db.add(
        DurableJob(
            org_id=req.org_id,
            request_id=req.id,
            kind="EXTRACT",
            source_revision=req.conversation_revision,
            dedupe_key=f"extract:{req.id}:{req.conversation_revision}:{suffix}",
        )
    )


def append_draft(db, req, values, author_id=None, reason=None):
    req.draft_version += 1
    row = ReviewedDraftRevision(
        org_id=req.org_id,
        request_id=req.id,
        version=req.draft_version,
        source_revision=req.conversation_revision,
        data=values,
        author_id=author_id,
        reason=reason,
    )
    db.add(row)
    return row


def submit(db, actor, data, key):
    tenant(actor)
    require(
        key and len(key) <= 150,
        "IDEMPOTENCY_KEY_REQUIRED",
        "Supply an Idempotency-Key (1–150 characters)",
    )
    key_hash = digest(f"{actor.org_id}:{actor.user_id}:{key}")
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key_hash[:15], 16)})
    body_hash = digest(json.dumps(data.model_dump(), sort_keys=True))
    prior = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.org_id == actor.org_id,
            IdempotencyRecord.user_id == actor.user_id,
            IdempotencyRecord.key == key,
        )
    )
    if prior:
        require(
            prior.body_hash == body_hash,
            "IDEMPOTENCY_CONFLICT",
            "This key was already used with different content",
            409,
        )
        return queries.request_for(db, actor, prior.request_id)
    assignment = db.scalar(
        select(TenantUnitAssignment).where(
            TenantUnitAssignment.org_id == actor.org_id,
            TenantUnitAssignment.user_id == actor.user_id,
            TenantUnitAssignment.unit_id == data.unit_id,
        )
    )
    require(assignment is not None, "FORBIDDEN", "Select one of your assigned units", 403)
    rid = uid()
    req = MaintenanceRequest(
        id=rid,
        org_id=actor.org_id,
        tenant_id=actor.user_id,
        unit_id=data.unit_id,
        title=data.title,
        original_message=data.description,
        thread_id=f"org:{actor.org_id}:request:{rid}:{uid()}",
        conversation_revision=1,
        draft_version=0,
    )
    db.add(req)
    db.flush()
    db.add(
        RequestMessage(
            org_id=actor.org_id,
            request_id=req.id,
            author_id=actor.user_id,
            kind="ORIGINAL",
            body=data.description,
            revision=1,
        )
    )
    append_draft(db, req, ReviewedValues(description=data.description).model_dump(mode="json"))
    schedule_extraction(db, req)
    db.add(
        IdempotencyRecord(
            org_id=actor.org_id,
            user_id=actor.user_id,
            key=key,
            body_hash=body_hash,
            request_id=req.id,
        )
    )
    audit(db, actor, req.id, "request.submitted")
    db.commit()
    return req


def add_message(db, actor, request_id, body):
    tenant(actor)
    req = queries.request_for(db, actor, request_id, lock=True)
    require(req.status != "REJECTED", "INVALID_STATE", "Rejected requests are closed", 409)
    require(
        not req.pending_command_id,
        "COMMAND_PENDING",
        "A staff action is processing; retry shortly",
        409,
    )
    require(
        req.conversation_revision < 30,
        "CONVERSATION_LIMIT",
        "Conversation limit reached; contact staff",
    )
    req.conversation_revision += 1
    db.add(
        RequestMessage(
            org_id=req.org_id,
            request_id=req.id,
            author_id=actor.user_id,
            body=body,
            kind="TENANT_REPLY",
            revision=req.conversation_revision,
        )
    )
    if req.status != "APPROVED":
        transition(req, "PROCESSING")
        req.processing_error = None
        schedule_extraction(db, req)
    audit(db, actor, req.id, "message.added")
    db.commit()
    return req


def version_guard(req, expected_version, source_revision):
    require(
        req.draft_version == expected_version and req.conversation_revision == source_revision,
        "STALE_REVIEW",
        "The conversation or draft changed. Reload and review the latest version.",
        409,
    )


def edit_draft(db, actor, request_id, data):
    staff(actor)
    req = queries.request_for(db, actor, request_id, lock=True)
    require(
        req.status not in {"APPROVED", "REJECTED"}, "INVALID_STATE", "This request is closed", 409
    )
    require(not req.pending_command_id, "COMMAND_PENDING", "Wait for the pending staff action", 409)
    version_guard(req, data.expected_version, data.source_revision)
    before = queries.draft(db, req).data
    values = data.values.model_dump(mode="json")
    values["assigned_team"] = TEAMS[values["category"]]
    row = append_draft(db, req, values, actor.user_id, data.reason)
    for field, value in values.items():
        if before.get(field) != value:
            db.add(
                FieldCorrection(
                    org_id=req.org_id,
                    request_id=req.id,
                    draft_version=req.draft_version,
                    field=field,
                    previous_value=before.get(field),
                    new_value=value,
                    author_id=actor.user_id,
                    reason=data.reason,
                )
            )
    if req.status in {"PROCESSING", "PROCESSING_FAILED"}:
        transition(req, "NEEDS_REVIEW")
    audit(db, actor, req.id, "draft.revised", {"version": req.draft_version})
    # The durable revision command advances the graph without invoking the model.
    _enqueue(db, actor, req, "revise", data, f"draft:{req.id}:{req.draft_version}")
    db.commit()
    return row


def approval_guard(db, req):
    current = queries.draft(db, req)
    require(
        current.source_revision == req.conversation_revision,
        "STALE_DRAFT",
        "Review and save the draft against the latest conversation",
        409,
    )
    unit = db.scalar(select(Unit).where(Unit.id == req.unit_id, Unit.org_id == req.org_id))
    require(unit is not None, "INCOMPLETE", "A verified property and unit are required", 422)
    missing = completeness(current.data)
    require(not missing, "INCOMPLETE", "Complete reviewed fields: " + ", ".join(missing), 422)
    latest = db.scalar(
        select(AIExtractionRevision)
        .where(AIExtractionRevision.request_id == req.id)
        .order_by(AIExtractionRevision.created_at.desc())
    )
    if latest and latest.data.get("multiple_issues_detected"):
        require(
            current.data.get("multiple_issues_resolved"),
            "MULTIPLE_ISSUES",
            "Separate unrelated issues and explicitly confirm one issue remains",
            422,
        )


def _enqueue(db, actor, req, action, data, key):
    command = WorkflowCommand(
        id=uid(),
        org_id=req.org_id,
        request_id=req.id,
        operation_key=key,
        actor_id=actor.user_id,
        action=action,
        draft_version=req.draft_version,
        source_revision=req.conversation_revision,
        payload={"note": getattr(data, "note", "")},
    )
    db.add(command)
    db.flush()
    req.pending_command_id = command.id
    db.add(
        DurableJob(
            org_id=req.org_id,
            request_id=req.id,
            kind="COMMAND",
            source_revision=req.conversation_revision,
            command_id=command.id,
            dedupe_key=f"command:{command.id}",
        )
    )
    return command


def queue_action(db, actor, request_id, action, data, key):
    staff(actor)
    require(
        key and len(key) <= 100,
        "IDEMPOTENCY_KEY_REQUIRED",
        "Supply an Idempotency-Key (maximum 100 characters)",
    )
    req = queries.request_for(db, actor, request_id, lock=True)
    operation_key = f"{actor.user_id}:{key}"
    prior = db.scalar(
        select(WorkflowCommand).where(
            WorkflowCommand.org_id == actor.org_id, WorkflowCommand.operation_key == operation_key
        )
    )
    if prior:
        require(
            prior.request_id == req.id
            and prior.action == action
            and prior.draft_version == data.expected_version
            and prior.source_revision == data.source_revision
            and prior.payload == {"note": data.note},
            "IDEMPOTENCY_CONFLICT",
            "Action key was reused with different content",
            409,
        )
        return prior
    require(
        req.status not in {"APPROVED", "REJECTED"}, "INVALID_STATE", "This request is closed", 409
    )
    require(
        not req.pending_command_id, "COMMAND_PENDING", "Another staff action is processing", 409
    )
    version_guard(req, data.expected_version, data.source_revision)
    if action == "approve":
        approval_guard(db, req)
    if action in {"clarify", "reject"}:
        require(
            bool(data.note.strip()),
            "NOTE_REQUIRED",
            "Enter the clarification question or rejection reason",
            422,
        )
    command = _enqueue(db, actor, req, action, data, operation_key)
    audit(db, actor, req.id, f"workflow.{action}.queued", {"command_id": command.id})
    db.commit()
    return command


def apply_command(db, command_id):
    """Replay-safe transaction, invoked only after a graph interrupt resumes."""
    from app.models import Membership
    from app.services.auth import Actor

    cmd = db.get(WorkflowCommand, command_id)
    require(cmd is not None, "INVALID_COMMAND", "Durable command not found", 404)
    req = db.scalar(
        select(MaintenanceRequest)
        .where(MaintenanceRequest.id == cmd.request_id, MaintenanceRequest.org_id == cmd.org_id)
        .with_for_update()
    )
    if cmd.status != "PENDING":
        return cmd.result or {}
    membership = db.scalar(
        select(Membership).where(
            Membership.org_id == cmd.org_id,
            Membership.user_id == cmd.actor_id,
            Membership.active.is_(True),
        )
    )
    require(membership is not None, "FORBIDDEN", "Actor is no longer a member", 403)
    who = Actor(cmd.actor_id, cmd.org_id, membership.role)
    staff(who)
    version_guard(req, cmd.draft_version, cmd.source_revision)
    require(
        req.pending_command_id == cmd.id, "STALE_COMMAND", "Command no longer owns the review", 409
    )
    if cmd.action == "approve":
        approval_guard(db, req)
        current = queries.draft(db, req)
        order = queries.order_for(db, req)
        if not order:
            order = WorkOrder(
                id=uid(),
                org_id=req.org_id,
                request_id=req.id,
                data=current.data.copy(),
                approved_by=who.user_id,
                approved_draft_version=current.version,
                source_revision=current.source_revision,
            )
            db.add(order)
        transition(req, "APPROVED")
        notify(db, req, "Your maintenance request was approved. A work order is open.")
        result = {"work_order_id": order.id, "status": "APPROVED"}
    elif cmd.action == "clarify":
        require(req.conversation_revision < 30, "CONVERSATION_LIMIT", "Conversation limit reached")
        req.conversation_revision += 1
        db.add(
            RequestMessage(
                org_id=req.org_id,
                request_id=req.id,
                author_id=who.user_id,
                body=cmd.payload["note"],
                kind="STAFF_QUESTION",
                revision=req.conversation_revision,
            )
        )
        transition(req, "WAITING_FOR_TENANT")
        notify(db, req, "Staff has a question about your request.")
        result = {"status": req.status}
    elif cmd.action == "reject":
        transition(req, "REJECTED")
        notify(db, req, "Request rejected: " + cmd.payload["note"][:240])
        result = {"status": req.status}
    else:
        require(cmd.action == "revise", "INVALID_COMMAND", "Unknown review action")
        result = {"status": req.status}
    req.pending_command_id = None
    cmd.status, cmd.result = "APPLIED", result
    audit(db, who, req.id, f"workflow.{cmd.action}.applied", {"command_id": cmd.id, **result})
    db.commit()  # Approval, work order, receipt, audit and notification commit together.
    return result


def retry(db, actor, request_id):
    staff(actor)
    req = queries.request_for(db, actor, request_id, lock=True)
    require(
        req.status == "PROCESSING_FAILED" and not req.pending_command_id,
        "INVALID_STATE",
        "Only failed processing can be retried",
        409,
    )
    transition(req, "PROCESSING")
    req.processing_error = None
    schedule_extraction(db, req, uid())
    audit(db, actor, req.id, "processing.retried")
    db.commit()
    return req


def update_order(db, actor, order_id, data):
    staff(actor)
    order = db.scalar(
        select(WorkOrder)
        .where(WorkOrder.id == order_id, WorkOrder.org_id == actor.org_id)
        .with_for_update()
    )
    require(order is not None, "NOT_FOUND", "Work order not found", 404)
    require(
        order.version == data.expected_version, "STALE_REVIEW", "Work order changed; reload", 409
    )
    transition(order, data.status, ORDER_TRANSITIONS)
    if data.description:
        order.data = {**order.data, "description": data.description}
    order.version += 1
    audit(
        db,
        actor,
        order.id,
        "work_order.updated",
        {"status": order.status, "version": order.version},
    )
    req = queries.request_for(db, actor, order.request_id)
    notify(db, req, f"Work order status: {order.status.replace('_', ' ').lower()}.")
    db.commit()
    return order
