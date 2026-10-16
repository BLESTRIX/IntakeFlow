"""Explicit setup and account management; never run schema creation at API startup."""

import argparse
import getpass

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Membership, Organization, Unit, User
from app.services.auth import Actor, hasher


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("checkpoints")
    sub.add_parser("seed")
    user = sub.add_parser("create-user")
    user.add_argument("--email", required=True)
    user.add_argument("--name", required=True)
    user.add_argument("--organization", required=True)
    user.add_argument("--role", choices=["ADMIN", "STAFF", "TENANT"], required=True)
    assignment = sub.add_parser("assign-unit")
    assignment.add_argument("--email", required=True)
    assignment.add_argument("--unit", required=True)
    assignment.add_argument("--organization", required=True)
    sub.add_parser("drain-jobs")
    args = parser.parse_args()
    if args.command == "checkpoints":
        with PostgresSaver.from_conn_string(get_settings().checkpoint_url) as saver:
            saver.setup()
        print("PostgreSQL checkpoints initialized")
    elif args.command == "seed":
        from app.seed import seed

        seed()
    elif args.command == "drain-jobs":
        from app.tasks.worker import pending_jobs, process_job

        with SessionLocal() as db:
            ids = pending_jobs(db)
        for job_id in ids:
            print(job_id, process_job(job_id))
    else:
        with SessionLocal() as db:
            org = db.get(Organization, args.organization)
            if not org:
                parser.error("Organization ID not found")
            account = db.scalar(select(User).where(User.email == args.email.lower()))
            if args.command == "create-user":
                if not account:
                    password = getpass.getpass("Password (minimum 12 characters): ")
                    if len(password) < 12 or len(password) > 128:
                        parser.error("Password must contain 12–128 characters")
                    account = User(
                        email=args.email.lower(),
                        name=args.name,
                        password_hash=hasher.hash(password),
                    )
                    db.add(account)
                    db.flush()
                membership = db.scalar(
                    select(Membership).where(
                        Membership.org_id == org.id, Membership.user_id == account.id
                    )
                )
                if not membership:
                    db.add(Membership(org_id=org.id, user_id=account.id, role=args.role))
                else:
                    parser.error("Membership already exists")
            else:
                if not account:
                    parser.error("User not found")
                from app.schemas.api import AssignmentIn
                from app.services.management import assign_unit

                admin = db.scalar(
                    select(Membership).where(
                        Membership.org_id == org.id, Membership.role == "ADMIN"
                    )
                )
                if not admin:
                    parser.error("Organization needs an admin")
                if not db.scalar(select(Unit).where(Unit.id == args.unit, Unit.org_id == org.id)):
                    parser.error("Unit not found in organization")
                assign_unit(
                    db,
                    Actor(admin.user_id, org.id, "ADMIN"),
                    AssignmentIn(user_id=account.id, unit_id=args.unit),
                )
            db.commit()
            print("Account/membership assignment saved")


if __name__ == "__main__":
    main()
