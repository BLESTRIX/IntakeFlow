from datetime import timedelta

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import func, select

from app.ai.providers.base import ConfigurationError, ProviderResult, TemporaryProviderError
from app.ai.providers.demo import DemoProvider
from app.ai.runner import extract
from app.ai.schemas.extraction import EvidenceError, Extraction, validate_evidence
from app.ai.workflows.intake import build_graph
from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.models import AIExtractionRevision, Membership, ModelInvocation, WorkOrder, utcnow
from app.repositories import queries
from app.schemas.api import ReviewAction
from app.services import intake
from app.tasks.worker import process_job
from tests.conftest import sign_in
from tests.test_intake import finish_draft, job_for, submit


def sources(db, req):
    return [{"id": m.id, "kind": m.kind, "body": m.body} for m in queries.messages(db, req)]


class FailingProvider:
    name, model = "test", "failures-v1"

    def __init__(self, error):
        self.error, self.calls = error, 0

    def invoke(self, messages, repair=False):
        self.calls += 1
        raise self.error


def test_invalid_structured_output_one_repair(db, scenario):
    req = submit(db, scenario)

    class Invalid(DemoProvider):
        calls = 0

        def invoke(self, messages, repair=False):
            self.calls += 1
            return ProviderResult({"unexpected": "field"})

    provider = Invalid()
    with pytest.raises(ConfigurationError, match="malformed"):
        extract(db, job_for(db, req).id, sources(db, req), provider, sleep=lambda _: None)
    assert provider.calls == 2
    assert db.scalar(select(func.count()).select_from(ModelInvocation)) == 2


def test_exact_quotes_and_request_membership(db, scenario):
    req = submit(db, scenario)
    messages = sources(db, req)
    output = DemoProvider().invoke(messages).data
    output["evidence"][0]["message_id"] = "another-request-message"
    with pytest.raises(EvidenceError):
        validate_evidence(Extraction.model_validate(output), messages)
    output["evidence"][0]["message_id"] = messages[0]["id"]
    output["evidence"][0]["quote"] = "a fabricated source quote"
    with pytest.raises(EvidenceError):
        validate_evidence(Extraction.model_validate(output), messages)


def test_fabricated_evidence_job_fails_visibly(db, scenario):
    req = submit(db, scenario)

    class Fabricated(DemoProvider):
        def invoke(self, messages, repair=False):
            result = super().invoke(messages)
            result.data["evidence"][0]["quote"] = "made up"
            return result

    assert process_job(job_for(db, req).id, Fabricated()) == "FAILED"
    db.refresh(req)
    assert req.status == "PROCESSING_FAILED"
    assert "evidence" in req.processing_error
    assert db.scalar(select(func.count()).select_from(AIExtractionRevision)) == 0


@pytest.mark.parametrize(
    "error,calls", [(TemporaryProviderError("network"), 3), (ConfigurationError("auth"), 1)]
)
def test_retry_bound(db, scenario, error, calls):
    req = submit(db, scenario)
    provider = FailingProvider(error)
    with pytest.raises(ConfigurationError):
        extract(db, job_for(db, req).id, sources(db, req), provider, sleep=lambda _: None)
    assert provider.calls == calls
    assert job_for(db, req).model_calls == calls


def test_late_response_cannot_overwrite_newer_conversation(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)

    class Late(DemoProvider):
        def invoke(self, messages, repair=False):
            with SessionLocal() as other:
                intake.add_message(
                    other, actors["TENANT_a"], req.id, "It is actually in the bathroom."
                )
            return super().invoke(messages)

    assert process_job(job_for(db, req).id, Late()) == "SUPERSEDED"
    db.expire_all()
    db.refresh(req)
    assert req.conversation_revision == 2
    assert req.status == "PROCESSING"
    assert db.scalar(select(func.count()).select_from(AIExtractionRevision)) == 0
    assert queries.draft(db, req).version == 1


def test_recover_abandoned_lease_duplicate_delivery(db, scenario):
    req = submit(db, scenario)
    job = job_for(db, req)
    job.status, job.lease_until = "RUNNING", utcnow() - timedelta(seconds=1)
    db.commit()
    assert process_job(job.id) == "DONE"
    assert process_job(job.id) == "duplicate"
    assert db.scalar(select(func.count()).select_from(AIExtractionRevision)) == 1


def test_tenant_cannot_resume_approval_or_read_extractions(db, scenario, client):
    req = submit(db, scenario)
    headers = sign_in(client)
    assert (
        client.post(
            f"/api/v1/requests/{req.id}/approve",
            json={"expected_version": req.draft_version, "source_revision": 1},
            headers={**headers, "Idempotency-Key": "attack"},
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/requests/{req.id}/extractions").status_code == 403
    assert client.post("/api/v1/workflows/arbitrary/resume", headers=headers).status_code == 404


def test_cross_request_graph_envelope_rejected(db, scenario):
    req = submit(db, scenario)
    graph = build_graph(db, InMemorySaver())
    config = {"configurable": {"thread_id": "test-scoped"}}
    graph.invoke({"org_id": scenario[0]["ADMIN_b"].org_id, "request_id": "other-request"}, config)
    with pytest.raises(DomainError, match="scope mismatch"):
        graph.invoke(Command(resume={"job_id": job_for(db, req).id}), config)


def test_authorization_rechecked_when_command_executes(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    finish_draft(db, actors["STAFF_a"], req)
    db.refresh(req)
    intake.queue_action(
        db,
        actors["STAFF_a"],
        req.id,
        "approve",
        ReviewAction(expected_version=req.draft_version, source_revision=req.conversation_revision),
        "authorized-then-revoked",
    )
    member = db.scalar(select(Membership).where(Membership.user_id == actors["STAFF_a"].user_id))
    member.active = False
    db.commit()
    assert process_job(job_for(db, req, "COMMAND").id) == "FAILED"
    assert db.scalar(select(func.count()).select_from(WorkOrder)) == 0


def test_provider_outage_manual_path(db, scenario):
    actors, _ = scenario
    req = submit(db, scenario)
    assert (
        process_job(job_for(db, req).id, FailingProvider(ConfigurationError("unavailable")))
        == "FAILED"
    )
    finish_draft(db, actors["STAFF_a"], req)
    db.refresh(req)
    intake.queue_action(
        db,
        actors["STAFF_a"],
        req.id,
        "approve",
        ReviewAction(expected_version=req.draft_version, source_revision=req.conversation_revision),
        "manual",
    )
    assert process_job(job_for(db, req, "COMMAND").id) == "DONE"
    assert db.scalar(select(func.count()).select_from(WorkOrder)) == 1


def test_combined_retry_repair_budget_is_four_total_calls(db, scenario):
    req = submit(db, scenario)

    class Mixed(DemoProvider):
        calls = 0

        def invoke(self, messages, repair=False):
            self.calls += 1
            if self.calls <= 2:
                raise TemporaryProviderError("temporary")
            return ProviderResult({"malformed": True})

    provider = Mixed()
    with pytest.raises(ConfigurationError, match="malformed"):
        extract(db, job_for(db, req).id, sources(db, req), provider, sleep=lambda _: None)
    assert provider.calls == 4
    # Replay cannot spend a new model-call budget for this same durable job.
    with pytest.raises(ConfigurationError, match="call_budget_exhausted"):
        extract(db, job_for(db, req).id, sources(db, req), provider, sleep=lambda _: None)
    assert provider.calls == 4
