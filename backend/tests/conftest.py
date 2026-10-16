import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://intakeflow:intakeflow@localhost:5432/intakeflow_test"
)
os.environ["AI_PROVIDER"] = "demo"

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Base, Membership, Organization, Property, TenantUnitAssignment, Unit, User
from app.services.auth import Actor, hasher


@pytest.fixture(scope="session", autouse=True)
def database_ready():
    if not get_settings().database_url.rsplit("/", 1)[-1].startswith("intakeflow_test"):
        pytest.fail(
            "Tests truncate business data. DATABASE_URL must name intakeflow_test (or intakeflow_test_*)."
        )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alembic_version"))
    except Exception as exc:
        pytest.fail(
            f"PostgreSQL with migrations is required: {type(exc).__name__}. See README testing commands."
        )
    with PostgresSaver.from_conn_string(get_settings().checkpoint_url) as saver:
        saver.setup()


@pytest.fixture
def db():
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE " + ", ".join(f'"{t}"' for t in Base.metadata.tables) + " CASCADE")
        )
        conn.execute(text("TRUNCATE checkpoints, checkpoint_blobs, checkpoint_writes CASCADE"))
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture(scope="session")
def password_hash():
    return hasher.hash("testing-password-2026")


@pytest.fixture
def scenario(db, password_hash):
    actors, units = {}, {}
    for suffix in ["a", "b"]:
        org = Organization(name=f"Organization {suffix}")
        db.add(org)
        db.flush()
        for role in ["ADMIN", "STAFF", "TENANT"]:
            user = User(
                name=role, email=f"{role.lower()}-{suffix}@example.com", password_hash=password_hash
            )
            db.add(user)
            db.flush()
            db.add(Membership(org_id=org.id, user_id=user.id, role=role))
            actors[f"{role}_{suffix}"] = Actor(user.id, org.id, role)
        prop = Property(org_id=org.id, name="Cedar", address="24 Garden Road")
        db.add(prop)
        db.flush()
        unit = Unit(org_id=org.id, property_id=prop.id, label="A-101")
        db.add(unit)
        db.flush()
        db.add(
            TenantUnitAssignment(
                org_id=org.id, user_id=actors[f"TENANT_{suffix}"].user_id, unit_id=unit.id
            )
        )
        units[suffix] = unit
    db.commit()
    return actors, units


@pytest.fixture
def client(db):
    with TestClient(app) as client:
        yield client


def sign_in(client, email="tenant-a@example.com"):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testing-password-2026"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}
