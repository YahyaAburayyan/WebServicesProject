from enum import Enum

# usage of one shared enums values accross the whole project so there will be no errors in thhe naming 
class ApplicationStatus(str, Enum):
    submitted = "submitted"
    pre_checked = "pre_checked"
    survey_required = "survey_required"
    surveyed = "surveyed"
    legal_review = "legal_review"
    approved = "approved"
    certificate_issued = "certificate_issued"
    closed = "closed"
    rejected = "rejected"
    on_hold = "on_hold"
    missing_documents = "missing_documents"
    under_objection = "under_objection"


class ApplicationType(str, Enum):
    first_registration = "first_registration"
    ownership_transfer = "ownership_transfer"
    parcel_subdivision = "parcel_subdivision"
    parcel_merge = "parcel_merge"
    boundary_correction = "boundary_correction"
    certificate_request = "certificate_request"


class ApplicantType(str, Enum):
    citizen = "citizen"
    lawyer = "lawyer"
    company = "company"
    surveyor = "surveyor"
    representative = "representative"


class VerificationState(str, Enum):
    unverified = "unverified"
    verified = "verified"
    suspended = "suspended"


class DocumentStatus(str, Enum):
    pending_review = "pending_review"
    verified = "verified"
    rejected = "rejected"


class SurveyMilestone(str, Enum):
    assigned = "assigned"
    visit_scheduled = "visit_scheduled"
    arrived_on_site = "arrived_on_site"
    survey_started = "survey_started"
    survey_completed = "survey_completed"
    report_uploaded = "report_uploaded"
    registrar_reviewed = "registrar_reviewed"


class StaffRole(str, Enum):
    surveyor = "surveyor"
    registrar = "registrar"
