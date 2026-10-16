from sqlalchemy import select

from app.core.errors import require
from app.models import Membership, Property, TenantUnitAssignment, Unit, User
from app.services.auth import admin, hasher
from app.services.intake import audit


def create_property(db, actor, data):
    admin(actor)
    row = Property(org_id=actor.org_id, **data.model_dump())
    db.add(row)
    db.flush()
    audit(db, actor, row.id, "property.created")
    db.commit()
    return row


def create_unit(db, actor, property_id, data):
    admin(actor)
    require(
        db.scalar(
            select(Property).where(Property.id == property_id, Property.org_id == actor.org_id)
        )
        is not None,
        "NOT_FOUND",
        "Property not found",
        404,
    )
    row = Unit(org_id=actor.org_id, property_id=property_id, label=data.label)
    db.add(row)
    db.flush()
    audit(db, actor, row.id, "unit.created")
    db.commit()
    return row


def create_member(db, actor, data):
    admin(actor)
    require(
        db.scalar(select(User).where(User.email == str(data.email).lower())) is None,
        "EMAIL_EXISTS",
        "Account already exists; assign an existing account with the management CLI",
        409,
    )
    user = User(
        name=data.name, email=str(data.email).lower(), password_hash=hasher.hash(data.password)
    )
    db.add(user)
    db.flush()
    member = Membership(org_id=actor.org_id, user_id=user.id, role=data.role)
    db.add(member)
    audit(db, actor, user.id, "membership.created", {"role": data.role})
    db.commit()
    return {"id": user.id, "name": user.name, "email": user.email, "role": member.role}


def assign_unit(db, actor, data):
    admin(actor)
    require(
        db.scalar(
            select(Membership).where(
                Membership.org_id == actor.org_id,
                Membership.user_id == data.user_id,
                Membership.role == "TENANT",
                Membership.active.is_(True),
            )
        )
        is not None,
        "NOT_FOUND",
        "Active tenant membership not found",
        404,
    )
    require(
        db.scalar(select(Unit).where(Unit.id == data.unit_id, Unit.org_id == actor.org_id))
        is not None,
        "NOT_FOUND",
        "Unit not found",
        404,
    )
    old = db.scalar(
        select(TenantUnitAssignment).where(
            TenantUnitAssignment.org_id == actor.org_id,
            TenantUnitAssignment.user_id == data.user_id,
            TenantUnitAssignment.unit_id == data.unit_id,
        )
    )
    if old:
        return old
    row = TenantUnitAssignment(org_id=actor.org_id, **data.model_dump())
    db.add(row)
    audit(db, actor, data.user_id, "tenant.assigned", {"unit_id": data.unit_id})
    db.commit()
    return row


def edit_property(db, actor, property_id, data):
    admin(actor)
    row = db.scalar(
        select(Property)
        .where(Property.org_id == actor.org_id, Property.id == property_id)
        .with_for_update()
    )
    require(row is not None, "NOT_FOUND", "Property not found", 404)
    row.name, row.address = data.name, data.address
    audit(db, actor, row.id, "property.updated")
    db.commit()
    return row


def edit_unit(db, actor, unit_id, data):
    admin(actor)
    row = db.scalar(
        select(Unit).where(Unit.org_id == actor.org_id, Unit.id == unit_id).with_for_update()
    )
    require(row is not None, "NOT_FOUND", "Unit not found", 404)
    row.label = data.label
    audit(db, actor, row.id, "unit.updated")
    db.commit()
    return row


def edit_membership(db, actor, membership_id, data):
    admin(actor)
    # Serialize role changes so concurrent removals cannot eliminate every administrator.
    members = db.scalars(
        select(Membership)
        .where(Membership.org_id == actor.org_id)
        .order_by(Membership.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    row = next((m for m in members if m.id == membership_id), None)
    require(row is not None, "NOT_FOUND", "Membership not found", 404)
    if row.role == "ADMIN" and row.active and (data.role != "ADMIN" or not data.active):
        require(
            sum(m.role == "ADMIN" and m.active for m in members) > 1,
            "LAST_ADMIN",
            "Keep at least one active administrator",
            409,
        )
    row.role, row.active = data.role, data.active
    audit(db, actor, row.user_id, "membership.updated", {"role": row.role, "active": row.active})
    db.commit()
    return row


def remove_assignment(db, actor, assignment_id):
    admin(actor)
    row = db.scalar(
        select(TenantUnitAssignment)
        .where(
            TenantUnitAssignment.org_id == actor.org_id, TenantUnitAssignment.id == assignment_id
        )
        .with_for_update()
    )
    require(row is not None, "NOT_FOUND", "Assignment not found", 404)
    audit(db, actor, row.user_id, "tenant.unassigned", {"unit_id": row.unit_id})
    db.delete(row)
    db.commit()
    return {"message": "Assignment removed"}
