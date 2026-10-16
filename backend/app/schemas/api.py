from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Role(StrEnum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    TENANT = "TENANT"


class Category(StrEnum):
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    HVAC = "HVAC"
    APPLIANCE = "APPLIANCE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class RequestStatus(StrEnum):
    PROCESSING = "PROCESSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    WAITING_FOR_TENANT = "WAITING_FOR_TENANT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"


class Priority(StrEnum):
    ROUTINE = "ROUTINE"
    PRIORITY = "PRIORITY"
    URGENT = "URGENT"


class RegisterIn(Strict):
    organization_name: str = Field(min_length=2, max_length=150)
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    timezone: str = "Asia/Karachi"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Use an IANA timezone") from exc
        return value


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    organization_id: str | None = None


class PropertyIn(Strict):
    name: str = Field(min_length=2, max_length=150)
    address: str = Field(min_length=3, max_length=300)


class UnitIn(Strict):
    label: str = Field(min_length=1, max_length=80)


class MemberIn(Strict):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Role


class AssignmentIn(Strict):
    user_id: str
    unit_id: str


class MembershipPatch(Strict):
    role: Role
    active: bool


class RequestIn(Strict):
    unit_id: str
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=10, max_length=5000)


class MessageIn(Strict):
    body: str = Field(min_length=1, max_length=5000)


class ReviewedValues(Strict):
    category: Category = Category.UNKNOWN
    room_or_area: str | None = Field(default=None, max_length=300)
    affected_item: str | None = Field(default=None, max_length=300)
    description: str = Field(default="", max_length=5000)
    priority: Priority | None = None
    assigned_team: str = Field(default="General maintenance", max_length=80)
    multiple_issues_resolved: bool = False


class DraftPatch(Strict):
    expected_version: int = Field(ge=0)
    source_revision: int = Field(ge=1)
    values: ReviewedValues
    reason: str | None = Field(default=None, max_length=500)


class ReviewAction(Strict):
    expected_version: int = Field(ge=0)
    source_revision: int = Field(ge=1)
    note: str = Field(default="", max_length=5000)


class WorkOrderPatch(Strict):
    expected_version: int = Field(ge=1)
    status: str = Field(pattern="^(OPEN|IN_PROGRESS|COMPLETED|CANCELED)$")
    description: str | None = Field(default=None, min_length=10, max_length=5000)
