import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.models import Membership, User
from app.repositories import queries
from app.services.auth import Actor
from app.services.intake import add_message
from tests.test_intake import job_for, submit


def test_database_protects_original_and_revisions(db, scenario):
    req = submit(db, scenario)
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE request_messages SET body='changed' WHERE request_id=:r"), {"r": req.id}
        )
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(
            text("UPDATE maintenance_requests SET original_message='changed' WHERE id=:r"),
            {"r": req.id},
        )
    db.rollback()


def test_same_organization_tenants_are_isolated(db, scenario, password_hash):
    req = submit(db, scenario)
    org_id = scenario[0]["TENANT_a"].org_id
    user = User(email="other-tenant@example.com", name="Other Tenant", password_hash=password_hash)
    db.add(user)
    db.flush()
    db.add(Membership(org_id=org_id, user_id=user.id, role="TENANT"))
    db.commit()
    from app.core.errors import DomainError

    with pytest.raises(DomainError, match="not found"):
        queries.request_for(db, Actor(user.id, org_id, "TENANT"), req.id)


def test_checkpoint_survives_separate_worker_processes(db, scenario):
    req = submit(db, scenario)
    first_job = job_for(db, req).id

    def execute(job_id):
        # UUID is database generated, never tenant-supplied shell text. No shell involved.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.tasks.worker import process_job; import sys; print(process_job(sys.argv[1]))",
                job_id,
            ],
            capture_output=True,
            text=True,
            timeout=40,
            check=True,
        )
        assert "DONE" in result.stdout

    execute(first_job)
    db.expire_all()
    add_message(db, scenario[0]["TENANT_a"], req.id, "The sink is in the kitchen.")
    execute(job_for(db, req).id)
    db.expire_all()
    db.refresh(req)
    assert req.status == "NEEDS_REVIEW"
    assert req.conversation_revision == 2
    assert queries.draft(db, req).source_revision == 1
