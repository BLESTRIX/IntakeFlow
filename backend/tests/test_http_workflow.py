from sqlalchemy import select

from app.models import DurableJob
from app.tasks.worker import process_job
from tests.conftest import sign_in


def drain(db, request_id):
    ids = db.scalars(
        select(DurableJob.id)
        .where(DurableJob.request_id == request_id, DurableJob.status == "PENDING")
        .order_by(DurableJob.created_at)
    ).all()
    db.commit()
    for job_id in ids:
        process_job(job_id)
    db.expire_all()


def test_http_workflow_and_order_updates(client, scenario, db):
    headers = sign_in(client)
    unit = scenario[1]["a"]
    payload = {
        "unit_id": unit.id,
        "title": "Leaking sink",
        "description": "The sink has been leaking since yesterday.",
    }
    response = client.post(
        "/api/v1/requests", json=payload, headers={**headers, "Idempotency-Key": "http-submit"}
    )
    assert response.status_code == 201, response.text
    rid = response.json()["id"]
    assert "thread_id" not in response.json()
    drain(db, rid)
    client.post("/api/v1/auth/logout", headers=headers)
    headers = sign_in(client, "staff-a@example.com")
    detail = client.get(f"/api/v1/requests/{rid}").json()
    review = {
        "expected_version": detail["draft_version"],
        "source_revision": detail["conversation_revision"],
        "note": "Which room is affected?",
    }
    assert (
        client.post(
            f"/api/v1/requests/{rid}/request-clarification",
            json=review,
            headers={**headers, "Idempotency-Key": "http-clarify"},
        ).status_code
        == 202
    )
    drain(db, rid)
    client.post("/api/v1/auth/logout", headers=headers)
    headers = sign_in(client)
    assert (
        client.post(
            f"/api/v1/requests/{rid}/messages",
            json={"body": "It is the kitchen sink."},
            headers=headers,
        ).status_code
        == 200
    )
    drain(db, rid)
    assert client.get("/api/v1/notifications").json()["total"] > 0
    client.post("/api/v1/auth/logout", headers=headers)
    headers = sign_in(client, "staff-a@example.com")
    detail = client.get(f"/api/v1/requests/{rid}").json()
    values = {
        **detail["draft"]["data"],
        "room_or_area": "kitchen",
        "category": "PLUMBING",
        "priority": "PRIORITY",
    }
    response = client.patch(
        f"/api/v1/requests/{rid}/draft",
        json={
            "expected_version": detail["draft_version"],
            "source_revision": detail["conversation_revision"],
            "values": values,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    drain(db, rid)
    detail = client.get(f"/api/v1/requests/{rid}").json()
    response = client.post(
        f"/api/v1/requests/{rid}/approve",
        json={
            "expected_version": detail["draft_version"],
            "source_revision": detail["conversation_revision"],
        },
        headers={**headers, "Idempotency-Key": "http-approve"},
    )
    assert response.status_code == 202, response.text
    drain(db, rid)
    orders = client.get("/api/v1/work-orders").json()["items"]
    assert len(orders) == 1
    order = orders[0]
    assert (
        client.patch(
            f"/api/v1/work-orders/{order['id']}",
            json={"expected_version": 1, "status": "COMPLETED"},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/work-orders/{order['id']}",
            json={"expected_version": 1, "status": "IN_PROGRESS"},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/work-orders/{order['id']}",
            json={"expected_version": 2, "status": "COMPLETED"},
            headers=headers,
        ).status_code
        == 200
    )
    approved_data = client.get(f"/api/v1/work-orders/{order['id']}").json()["data"]
    client.post("/api/v1/auth/logout", headers=headers)
    headers = sign_in(client)
    assert (
        client.post(
            f"/api/v1/requests/{rid}/messages",
            json={"body": "Thank you for fixing it."},
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/work-orders/{order['id']}").json()["data"] == approved_data
    assert client.get(f"/api/v1/requests/{rid}").json()["status"] == "APPROVED"
    assert not db.scalars(
        select(DurableJob).where(DurableJob.request_id == rid, DurableJob.status == "PENDING")
    ).all()
