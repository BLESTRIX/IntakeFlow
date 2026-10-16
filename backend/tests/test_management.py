import pytest
from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Membership, TenantUnitAssignment
from app.schemas.api import MembershipPatch, PropertyIn, UnitIn
from app.services import management


def test_admin_management_scope_and_last_admin(db, scenario):
    actors, units = scenario
    with pytest.raises(DomainError, match="Administrator"):
        management.edit_unit(db, actors["STAFF_a"], units["a"].id, UnitIn(label="A-111"))
    with pytest.raises(DomainError, match="not found"):
        management.edit_unit(db, actors["ADMIN_a"], units["b"].id, UnitIn(label="A-111"))
    db.rollback()
    admin_member = db.scalar(
        select(Membership).where(Membership.user_id == actors["ADMIN_a"].user_id)
    )
    with pytest.raises(DomainError, match="at least one"):
        management.edit_membership(
            db, actors["ADMIN_a"], admin_member.id, MembershipPatch(role="STAFF", active=True)
        )
    db.rollback()
    changed = management.edit_unit(db, actors["ADMIN_a"], units["a"].id, UnitIn(label="A-111"))
    assert changed.label == "A-111"
    prop = management.edit_property(
        db,
        actors["ADMIN_a"],
        units["a"].property_id,
        PropertyIn(name="New name", address="42 Garden Lane"),
    )
    assert prop.name == "New name"
    assignment = db.scalar(
        select(TenantUnitAssignment).where(
            TenantUnitAssignment.user_id == actors["TENANT_a"].user_id
        )
    )
    management.remove_assignment(db, actors["ADMIN_a"], assignment.id)
    assert db.get(TenantUnitAssignment, assignment.id) is None
