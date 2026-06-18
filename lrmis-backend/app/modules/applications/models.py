"""Pydantic request models for the Land Application module (Student 1).
Typed with the shared enums so FastAPI auto-rejects bad values with 422."""
from pydantic import BaseModel, Field

from app.common.enums import ApplicationType, ApplicationStatus


class ApplicantRef(BaseModel):
    applicant_id: str
    applicant_type: str
    submitted_by_representative: bool = False


class ParcelRef(BaseModel):
    parcel_id: str | None = None
    parcel_number: str
    block_number: str
    basin_number: str
    zone_id: str


class ApplicationCreate(BaseModel):
    application_type: ApplicationType
    applicant_ref: ApplicantRef
    parcel_ref: ParcelRef
    description: str | None = None
    priority: str = "normal"
    tags: list[str] = []


class TransitionRequest(BaseModel):
    target_state: ApplicationStatus
    note: str | None = None
    actor_type: str = "registrar"
    actor_id: str = "staff_unknown"


class HoldRequest(BaseModel):
    reason: str = Field(min_length=3)
    actor_type: str = "registrar"
    actor_id: str = "staff_unknown"


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3)   # mandatory rejection reason
    actor_type: str = "registrar"
    actor_id: str = "staff_unknown"


class CertificateRequest(BaseModel):
    certificate_type: str = "ownership_certificate"
    issued_by: str = "registrar_unknown"