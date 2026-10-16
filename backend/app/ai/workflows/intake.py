"""Checkpoints coordinate review; the business DB remains authoritative."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select

from app.ai.prompts.extraction import PROMPT_VERSION
from app.ai.runner import extract
from app.ai.schemas.extraction import SCHEMA_VERSION
from app.core.errors import DomainError, require
from app.models import AIExtractionRevision, DurableJob, MaintenanceRequest, WorkflowCommand
from app.repositories import queries
from app.services.intake import append_draft, apply_command
from app.services.states import TEAMS, transition


class IntakeState(TypedDict, total=False):
    org_id: str
    request_id: str
    job_id: str
    kind: str
    source_revision: int
    messages: list[dict]
    data: dict | None
    failure: str | None
    provider: str
    model: str
    terminal: bool


def build_graph(db, checkpointer, provider=None):
    def review(state):
        # No writes before the interrupt: this node is restarted on every resume.
        envelope = interrupt(
            {"request_id": state["request_id"], "awaiting": "authorized_review_or_extraction"}
        )
        job = db.get(DurableJob, envelope["job_id"])
        require(
            job is not None
            and job.org_id == state["org_id"]
            and job.request_id == state["request_id"],
            "FORBIDDEN",
            "Workflow job scope mismatch",
            403,
        )
        db.commit()
        return {
            "job_id": job.id,
            "kind": job.kind,
            "source_revision": job.source_revision,
            "data": None,
            "failure": None,
            "terminal": False,
        }

    def load(state):
        req = db.get(MaintenanceRequest, state["request_id"])
        require(req.org_id == state["org_id"], "FORBIDDEN", "Workflow scope mismatch", 403)
        snapshot = [
            {"id": m.id, "kind": m.kind, "body": m.body}
            for m in queries.messages(db, req)
            if m.revision <= state["source_revision"]
        ]
        db.commit()
        return {"messages": snapshot}

    def inference(state):
        existing = db.scalar(
            select(AIExtractionRevision).where(AIExtractionRevision.job_id == state["job_id"])
        )
        if existing:
            db.commit()
            return {"data": existing.data, "provider": existing.provider, "model": existing.model}
        req = db.get(MaintenanceRequest, state["request_id"])
        stale = req.conversation_revision != state["source_revision"] or req.status in {
            "APPROVED",
            "REJECTED",
        }
        db.commit()
        if stale:
            return {"failure": "superseded", "data": None}
        try:
            parsed, name, model = extract(db, state["job_id"], state["messages"], provider)
            return {
                "data": parsed.model_dump(mode="json"),
                "provider": name,
                "model": model,
                "failure": None,
            }
        except Exception as exc:
            db.rollback()
            return {
                "failure": str(exc)
                if type(exc).__name__ == "ConfigurationError"
                else "extraction_failed",
                "data": None,
            }

    def persist(state):
        db.expire_all()  # Discard objects read before the external model call.
        req = db.scalar(
            select(MaintenanceRequest)
            .where(MaintenanceRequest.id == state["request_id"])
            .with_for_update()
        )
        job = db.get(DurableJob, state["job_id"])
        # A late result never mutates a newer conversation, draft, or approved request.
        if req.conversation_revision != state["source_revision"] or req.status in {
            "APPROVED",
            "REJECTED",
        }:
            job.status = "SUPERSEDED"
        elif state.get("failure"):
            job.status, job.error = "FAILED", state["failure"][:200]
            if req.status == "PROCESSING":
                transition(req, "PROCESSING_FAILED")
                req.processing_error = (
                    "AI processing failed (" + job.error + "). Staff can process manually."
                )
        else:
            existing = db.scalar(
                select(AIExtractionRevision).where(AIExtractionRevision.job_id == job.id)
            )
            if not existing:
                db.add(
                    AIExtractionRevision(
                        org_id=req.org_id,
                        request_id=req.id,
                        job_id=job.id,
                        source_revision=state["source_revision"],
                        data=state["data"],
                        provider=state["provider"],
                        model=state["model"],
                        prompt_version=PROMPT_VERSION,
                        schema_version=SCHEMA_VERSION,
                    )
                )
                current = queries.draft(db, req)
                if current.author_id is None and req.draft_version == 1:
                    data = state["data"]
                    append_draft(
                        db,
                        req,
                        {
                            **current.data,
                            "category": data["category"],
                            "room_or_area": data["room_or_area"],
                            "affected_item": data["affected_item"],
                            "description": data["summary"],
                            "assigned_team": TEAMS[data["category"]],
                        },
                    )
            if req.status == "PROCESSING":
                transition(req, "NEEDS_REVIEW")
            req.processing_error = None
            job.status = "DONE"
        db.commit()
        return {}

    def action(state):
        job = db.get(DurableJob, state["job_id"])
        cmd = db.get(WorkflowCommand, job.command_id)
        require(
            cmd is not None
            and cmd.org_id == state["org_id"]
            and cmd.request_id == state["request_id"],
            "FORBIDDEN",
            "Workflow command scope mismatch",
            403,
        )
        try:
            apply_command(db, cmd.id)
        except DomainError as exc:
            db.rollback()
            cmd = db.get(WorkflowCommand, job.command_id)
            req = db.scalar(
                select(MaintenanceRequest)
                .where(MaintenanceRequest.id == state["request_id"])
                .with_for_update()
            )
            if cmd.status == "PENDING":
                cmd.status, cmd.result = "REJECTED", {"code": exc.code, "message": exc.message}
            if req.pending_command_id == cmd.id:
                req.pending_command_id = None
                req.processing_error = exc.message
            job.status, job.error = "FAILED", exc.code
            db.commit()
        else:
            job.status = "DONE"
            db.commit()
        req = db.get(MaintenanceRequest, state["request_id"])
        terminal = req.status in {"APPROVED", "REJECTED"}
        db.commit()
        return {"terminal": terminal}

    graph = StateGraph(IntakeState)
    graph.add_node("review", review)
    graph.add_node("load", load)
    graph.add_node("extract", inference)
    graph.add_node("persist", persist)
    graph.add_node("action", action)
    graph.add_edge(START, "review")
    graph.add_conditional_edges("review", lambda s: "load" if s["kind"] == "EXTRACT" else "action")
    graph.add_edge("load", "extract")
    graph.add_edge("extract", "persist")
    graph.add_edge("persist", "review")
    graph.add_conditional_edges("action", lambda s: END if s["terminal"] else "review")
    return graph.compile(checkpointer=checkpointer)
