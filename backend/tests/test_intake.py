from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.models import AIExtractionRevision, DurableJob, MaintenanceRequest, WorkOrder
from app.repositories import queries
from app.schemas.api import DraftPatch, RequestIn, ReviewAction, ReviewedValues
from app.services import intake
from app.tasks.worker import process_job
from tests.conftest import sign_in


def submit(db, scenario, description="The sink has been leaking since yesterday."):
    actors, units = scenario
    return intake.submit(
        db,
        actors["TENANT_a"],
        RequestIn(unit_id=units["a"].id, title="Leaking sink", description=description),
        "submit-key",
    )


def job_for(db, req, kind="EXTRACT"):
    return db.scalar(
        select(DurableJob)
        .where(DurableJob.request_id == req.id, DurableJob.kind == kind)
        .order_by(DurableJob.created_at.desc())
    )


def finish_draft(db, actor, req):
    db.refresh(req)
    result = intake.edit_draft(
        db,
        actor,
        req.id,
        DraftPatch(
            expected_version=req.draft_version,
            source_revision=req.conversation_revision,
            values=ReviewedValues(
                category="PLUMBING",
                room_or_area="kitchen",
                affected_item="sink",
                description="The sink leaks into the cupboard underneath.",
                priority="PRIORITY",
            ),
            reason="Verified from tenant conversation",
        ),
    )
    process_job(job_for(db, req, "COMMAND").id)
    db.expire_all()
    return result


def test_submission_idempotency_and_isolation(db, scenario, client):
    actors, units = scenario
    req = submit(db, scenario)
    duplicate = submit(db, scenario)
    assert req.id == duplicate.id
    assert db.scalar(select(func.count()).select_from(MaintenanceRequest)) == 1
    with pytest.raises(DomainError, match="different content"):
        submit(db, scenario, "The sink is definitely broken in a new way.")
    db.rollback()
    with pytest.raises(DomainError):
        intake.submit(
            db,
            actors["TENANT_a"],
            RequestIn(
                unit_id=units["b"].id, title="Leak", description="The sink leaks in the kitchen."
            ),
            "other",
        )
    db.rollback()
    sign_in(client, "staff-b@example.com")
    assert client.get(f"/api/v1/requests/{req.id}").status_code == 404
    assert client.get("/api/v1/requests").json()["total"] == 0


def test_manual_processing_and_single_work_order(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    finish_draft(db, actors["STAFF_a"], req)
    db.refresh(req)
    data = ReviewAction(
        expected_version=req.draft_version, source_revision=req.conversation_revision
    )
    command = intake.queue_action(db, actors["STAFF_a"], req.id, "approve", data, "approve-key")
    assert command.status == "PENDING"
    job = job_for(db, req, "COMMAND")
    assert process_job(job.id) == "DONE"
    assert process_job(job.id) == "duplicate"
    assert intake.apply_command(db, command.id)["status"] == "APPROVED"
    assert db.scalar(select(func.count()).select_from(WorkOrder)) == 1


def test_real_graph_clarification_restart_corrections(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    assert process_job(job_for(db, req).id) == "DONE"
    db.expire_all()
    db.refresh(req)
    assert req.status == "NEEDS_REVIEW"
    extraction = db.scalar(select(AIExtractionRevision))
    assert extraction.data["room_or_area"] is None
    assert "room_or_area" in extraction.data["missing_information"]
    intake.queue_action(
        db,
        actors["STAFF_a"],
        req.id,
        "clarify",
        ReviewAction(
            expected_version=req.draft_version,
            source_revision=req.conversation_revision,
            note="Which room is affected?",
        ),
        "question-key",
    )
    # Each process_job opens a fresh saver/session, like a worker restart while paused.
    assert process_job(job_for(db, req, "COMMAND").id) == "DONE"
    db.expire_all()
    db.refresh(req)
    assert req.status == "WAITING_FOR_TENANT"
    intake.add_message(db, actors["TENANT_a"], req.id, "It is the kitchen sink.")
    assert process_job(job_for(db, req).id) == "DONE"
    db.expire_all()
    db.refresh(req)
    assert queries.draft(db, req).source_revision != req.conversation_revision
    finish_draft(db, actors["STAFF_a"], req)
    db.refresh(req)
    corrected = queries.draft(db, req).data.copy()
    intake.add_message(
        db, actors["TENANT_a"], req.id, "There is also water under the kitchen cupboard."
    )
    assert process_job(job_for(db, req).id) == "DONE"
    db.expire_all()
    db.refresh(req)
    assert queries.draft(db, req).data == corrected
    with pytest.raises(DomainError, match="latest conversation"):
        intake.approval_guard(db, req)
    assert db.scalar(select(func.count()).select_from(AIExtractionRevision)) == 3


def test_concurrent_approval_one_command_and_order(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    finish_draft(db, actors["STAFF_a"], req)
    db.refresh(req)
    rid, version, revision = req.id, req.draft_version, req.conversation_revision

    def approve(key):
        with SessionLocal() as session:
            try:
                return intake.queue_action(
                    session,
                    actors["STAFF_a"],
                    rid,
                    "approve",
                    ReviewAction(expected_version=version, source_revision=revision),
                    key,
                ).id
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(approve, ["approval-1", "approval-2"]))
    assert sum(value == "COMMAND_PENDING" for value in result) == 1
    process_job(job_for(db, req, "COMMAND").id)
    assert db.scalar(select(func.count()).select_from(WorkOrder)) == 1


def test_optimistic_draft_conflict(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    version, revision = req.draft_version, req.conversation_revision
    finish_draft(db, actors["STAFF_a"], req)
    with pytest.raises(DomainError, match="changed"):
        intake.edit_draft(
            db,
            actors["STAFF_a"],
            req.id,
            DraftPatch(expected_version=version, source_revision=revision, values=ReviewedValues()),
        )
