"""Development-only alternative when Redis/Docker are unavailable. Runs the same services.
Production and the Compose demo use Celery + Beat. This helper verifies no Redis behavior.
"""
import time

from app.db.session import SessionLocal
from app.tasks.worker import pending_jobs, process_job

if __name__ == "__main__":
    while True:
        with SessionLocal() as db:
            ids = pending_jobs(db)
        for job_id in ids:
            process_job(job_id)
        time.sleep(0.5)
