import logging
from datetime import timedelta

from celery import Celery
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from sqlalchemy import or_, select, text

from app.ai.workflows.intake import build_graph
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import DurableJob, MaintenanceRequest, uid, utcnow
from app.services.auth import digest

settings = get_settings()
celery = Celery("intakeflow", broker=settings.redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={"discover-durable-jobs": {"task": "intakeflow.discover", "schedule": 5.0}},
)
logger = logging.getLogger("intakeflow.worker")


def pending_jobs(db):
    return db.scalars(
        select(DurableJob.id)
        .where(
            or_(
                DurableJob.status == "PENDING",
                (DurableJob.status == "RUNNING") & (DurableJob.lease_until < utcnow()),
            )
        )
        .order_by(DurableJob.created_at)
        .limit(100)
    ).all()


@celery.task(name="intakeflow.discover")
def discover():
    with SessionLocal() as db:
        ids = pending_jobs(db)
    for job_id in ids:
        run_job.delay(job_id)
    return len(ids)


def process_job(job_id, provider=None):
    with SessionLocal() as db:
        job = db.scalar(select(DurableJob).where(DurableJob.id == job_id).with_for_update())
        if not job or job.status not in {"PENDING", "RUNNING"}:
            return "duplicate"
        if job.status == "RUNNING" and job.lease_until and job.lease_until > utcnow():
            return "leased"
        token = uid()
        job.status, job.lease_token = "RUNNING", token
        job.lease_until = utcnow() + timedelta(seconds=settings.job_lease_seconds)
        job.attempts += 1
        req = db.get(MaintenanceRequest, job.request_id)
        if job.kind == "EXTRACT" and (
            req.status in {"APPROVED", "REJECTED"}
            or req.conversation_revision != job.source_revision
        ):
            job.status, job.lease_until = "SUPERSEDED", None
            db.commit()
            return "SUPERSEDED"
        thread_id, org_id, request_id = req.thread_id, req.org_id, req.id
        db.commit()
        lock_key = int(digest(f"workflow:{request_id}")[:15], 16)
        # Session advisory lock serializes checkpoints across workers. AUTOCOMMIT means
        # the model is never awaited inside an application transaction.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lock:
            acquired = lock.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_key})
            if not acquired:
                job.status, job.lease_until = "PENDING", None
                db.commit()
                return "busy"
            try:
                with PostgresSaver.from_conn_string(settings.checkpoint_url) as saver:
                    graph = build_graph(db, saver, provider)
                    config = {"configurable": {"thread_id": thread_id}}
                    state = graph.get_state(config)
                    if not state.values:
                        graph.invoke({"org_id": org_id, "request_id": request_id}, config)
                    elif state.next and state.next != ("review",):
                        graph.invoke(None, config)  # Finish an interrupted worker's pending nodes.
                    db.expire_all()
                    job = db.get(DurableJob, job_id)
                    if job.status == "RUNNING":
                        graph.invoke(Command(resume={"job_id": job_id}), config)
                    db.expire_all()
                    job = db.get(DurableJob, job_id)
                    if job.status == "RUNNING":
                        job.status = "DONE"
                    job.lease_until = None
                    db.commit()
                    return job.status
            except Exception as exc:
                db.rollback()
                job = db.get(DurableJob, job_id)
                # Infrastructure failure remains recoverable by Beat after the lease.
                job.error = "workflow_infrastructure:" + type(exc).__name__
                db.commit()
                logger.error("workflow_failure job=%s category=%s", job_id, type(exc).__name__)
                raise
            finally:
                lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})


@celery.task(name="intakeflow.run_job", acks_late=True, reject_on_worker_lost=True)
def run_job(job_id):
    return process_job(job_id)
