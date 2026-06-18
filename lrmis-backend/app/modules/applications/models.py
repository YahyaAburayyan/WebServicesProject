from pydantic import BaseModel, Field

# using the shared enums means FastAPI will auto-reject any invalid value with 422
from app.common.enums import ApplicationType, ApplicationStatus

# a one shared place the contains all the request body shapes for the posible applications in our system
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
    # reason is required, you can't reject without giving a reason
    reason: str = Field(min_length=3)
    actor_type: str = "registrar"
    actor_id: str = "staff_unknown"


class CertificateRequest(BaseModel):
    certificate_type: str = "ownership_certificate"
    issued_by: str = "registrar_unknown"
