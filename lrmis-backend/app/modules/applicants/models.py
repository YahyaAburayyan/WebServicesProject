from typing import Optional
from pydantic import BaseModel, Field
from app.common.enums import ApplicantType


class ApplicantIdentity(BaseModel):
    national_id: str = Field(min_length=5)
    verification_method: str = "otp_stub"


class ApplicantContacts(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class ApplicantAddress(BaseModel):
    city: str = ""
    neighborhood: str = ""
    zone_id: str = ""


class NotificationPrefs(BaseModel):
    on_status_change: bool = True
    on_missing_documents: bool = True
    on_certificate_ready: bool = True


class ApplicantPreferences(BaseModel):
    preferred_contact: str = "email"
    language: str = "en"
    notifications: NotificationPrefs = Field(default_factory=NotificationPrefs)


class PrivacySettings(BaseModel):
    share_contact_with_staff: bool = True
    show_in_public_registry: bool = False


class ApplicantCreate(BaseModel):
    applicant_id: Optional[str] = None
    full_name: str = Field(min_length=2)
    applicant_type: ApplicantType
    identity: ApplicantIdentity
    contacts: Optional[ApplicantContacts] = None
    address: Optional[ApplicantAddress] = None
    preferences: Optional[ApplicantPreferences] = None
    privacy: Optional[PrivacySettings] = None


class DocumentCreate(BaseModel):
    document_type: str = Field(min_length=2)
    document_name: Optional[str] = None
    applicant_id: Optional[str] = None
    notes: Optional[str] = None


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)
    applicant_id: Optional[str] = None
    actor_type: str = "applicant"


class ObjectionCreate(BaseModel):
    reason: str = Field(min_length=10)
    applicant_id: Optional[str] = None
    supporting_details: Optional[str] = None


class DocumentReviewRequest(BaseModel):
    status: str = Field(pattern="^(verified|rejected)$")
    reviewer_id: str = "registrar_001"
    review_notes: Optional[str] = None
