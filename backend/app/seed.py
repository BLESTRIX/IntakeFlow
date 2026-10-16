from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Membership, Organization, Property, TenantUnitAssignment, Unit, User
from app.schemas.api import RequestIn
from app.services.auth import Actor, hasher
from app.services.intake import submit

DEMO_PASSWORD = "IntakeFlow-demo-2026!"


def seed():
    settings = get_settings()
    if settings.environment == "production" or not settings.demo_accounts_enabled:
        raise RuntimeError("Demo accounts require DEMO_ACCOUNTS_ENABLED=true outside production")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "admin@demo.intakeflow.app")):
            print("Demo already seeded")
            return
        for index, org_name in enumerate(["Cedar Property Group", "Harbour Estates"]):
            org = Organization(name=org_name)
            db.add(org)
            db.flush()
            users = {}
            for role in ["ADMIN", "STAFF", "TENANT"]:
                email = f"{role.lower()}{'2' if index else ''}@demo.intakeflow.app"
                user = User(
                    name={"ADMIN": "Ayesha Khan", "STAFF": "Omar Ali", "TENANT": "Sara Ahmed"}[
                        role
                    ],
                    email=email,
                    password_hash=hasher.hash(DEMO_PASSWORD),
                )
                db.add(user)
                db.flush()
                db.add(Membership(org_id=org.id, user_id=user.id, role=role))
                users[role] = user
            prop = Property(
                org_id=org.id,
                name="Cedar Residences" if not index else "Harbour View",
                address="24 Garden Road, Karachi" if not index else "8 Marine Drive, Karachi",
            )
            db.add(prop)
            db.flush()
            for label in ["A-101", "A-102", "B-201"]:
                unit = Unit(org_id=org.id, property_id=prop.id, label=label)
                db.add(unit)
                db.flush()
                if label == "A-101":
                    db.add(
                        TenantUnitAssignment(
                            org_id=org.id, user_id=users["TENANT"].id, unit_id=unit.id
                        )
                    )
                    tenant_unit = unit
            db.commit()
            for i, (title, description) in enumerate(
                [
                    (
                        "Leaking sink",
                        "The sink has been leaking since yesterday and the cupboard underneath is wet.",
                    ),
                    (
                        "Bedroom air conditioner",
                        "The air conditioner in the bedroom is blowing warm air this morning.",
                    ),
                    ("Kitchen socket", "The kitchen socket sparks when I plug in the kettle."),
                ]
            ):
                submit(
                    db,
                    Actor(users["TENANT"].id, org.id, "TENANT"),
                    RequestIn(unit_id=tenant_unit.id, title=title, description=description),
                    f"seed-{i}",
                )
        print("Two demo organizations seeded. Demo password: " + DEMO_PASSWORD)
