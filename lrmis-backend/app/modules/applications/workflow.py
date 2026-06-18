"""Workflow state machine for land applications (STUDENT 1 core).
- ALLOWED_TRANSITIONS: which next states are legal from each state.
- guard(): the precondition rules from the project documentation.
Guards that depend on teammates' collections degrade gracefully: if the
evidence collection is empty/missing they return (False, reason) instead
of crashing, so this module is fully testable on its own."""
from app.common.enums import ApplicationStatus as S
from app.database import get_db

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    S.submitted:          {S.pre_checked, S.missing_documents, S.rejected, S.on_hold},
    S.pre_checked:        {S.survey_required, S.legal_review, S.missing_documents, S.rejected, S.on_hold},
    S.survey_required:    {S.surveyed, S.on_hold, S.rejected},
    S.surveyed:           {S.legal_review, S.under_objection, S.rejected, S.on_hold},
    S.legal_review:       {S.approved, S.rejected, S.under_objection, S.on_hold},
    S.approved:           {S.certificate_issued, S.rejected},
    S.certificate_issued: {S.closed},
    S.under_objection:    {S.legal_review, S.rejected, S.on_hold},
    S.missing_documents:  {S.submitted, S.pre_checked, S.rejected},
    S.on_hold:            {S.submitted, S.pre_checked, S.survey_required, S.legal_review, S.rejected},
    S.closed:             set(),
    S.rejected:           set(),
}


def can_transition(current: str, target: str) -> bool:
    """True if `target` is a legal next state from `current`."""
    return target in ALLOWED_TRANSITIONS.get(current, set())


def allowed_next(current: str) -> list[str]:
    return sorted(s.value for s in ALLOWED_TRANSITIONS.get(current, set()))


# ---------- precondition guards (project documentation rules) ---------------
def guard(app_doc: dict, target: str) -> tuple[bool, str]:
    """Return (allowed, reason_if_blocked) for moving app_doc to `target`."""
    db = get_db()
    app_id = app_doc.get("application_id")

    if target == S.pre_checked:
        # applicant AND parcel information must be complete
        applicant = app_doc.get("applicant_ref") or {}
        parcel = app_doc.get("parcel_ref") or {}
        if not applicant.get("applicant_id"):
            return False, "Applicant information is incomplete"
        if not (parcel.get("parcel_number") and parcel.get("zone_id")):
            return False, "Parcel information is incomplete"
        return True, ""

    if target == S.survey_required:
        # parcel location must be valid GeoJSON
        # seed_data.py stores the parcel identifier as parcel_code (not parcel_number),
        # so map the application's parcel_number to the parcels collection's parcel_code.
        parcel = app_doc.get("parcel_ref") or {}
        pdoc = db["parcels"].find_one({
            "parcel_code": parcel.get("parcel_number"),
            "zone_id": parcel.get("zone_id"),
        })
        geom = (pdoc or {}).get("geometry") or {}
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            return False, "Parcel has no valid GeoJSON location"
        return True, ""

    if target == S.surveyed:
        # a survey report must exist (Student 3's collection)
        report = db["survey_reports"].find_one({"application_id": app_id})
        if not report:
            return False, "No survey report found for this application"
        return True, ""

    if target == S.legal_review:
        # ownership documents must be uploaded (Student 2's collection)
        doc = db["application_documents"].find_one({
            "application_id": app_id,
            "document_type": {"$in": ["ownership_deed", "sale_contract"]},
            "status": {"$ne": "rejected"},
        })
        if not doc:
            return False, "Ownership documents are not uploaded"
        return True, ""

    if target == S.approved:
        # legal review must have been completed
        if app_doc.get("status") != S.legal_review:
            return False, "Application must be in legal_review before approval"
        return True, ""

    if target == S.certificate_issued:
        if app_doc.get("status") != S.approved:
            return False, "Application must be approved before issuing a certificate"
        return True, ""

    # on_hold, missing_documents, under_objection, rejected, closed: no extra precondition
    return True, ""