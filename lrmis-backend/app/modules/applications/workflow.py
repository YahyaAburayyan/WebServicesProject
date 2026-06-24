from app.common.enums import ApplicationStatus as S
from app.database import get_db


# defines which states you can go to from each state
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

# check if a vaild transition
def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def allowed_next(current: str) -> list[str]:
    return sorted(s.value for s in ALLOWED_TRANSITIONS.get(current, set()))


def guard(app_doc: dict, target: str) -> tuple[bool, str]:
    """
    Check if the application meets the preconditions for moving to target state.
    Returns (True, "") if allowed, or (False, reason) if blocked.
    """
    db = get_db()
    app_id = app_doc.get("application_id")

    if target == S.pre_checked:
        applicant = app_doc.get("applicant_ref") or {}
        parcel = app_doc.get("parcel_ref") or {}
        if not applicant.get("applicant_id"):
            return False, "Applicant information is incomplete"
        if not (parcel.get("parcel_number") and parcel.get("zone_id")):
            return False, "Parcel information is incomplete"
        return True, ""

    if target == S.survey_required:
        parcel = app_doc.get("parcel_ref") or {}
        pnum = parcel.get("parcel_number", "")
        zone = parcel.get("zone_id", "")
        # Match on parcel_code OR parcel_number (citizens may store either)
        parcel_doc = db["parcels"].find_one({
            "$or": [{"parcel_code": pnum}, {"parcel_number": pnum}],
            "zone_id": zone,
        }) if pnum else None
        geom = (parcel_doc or {}).get("geometry") or {}
        if geom.get("type") != "Polygon" or not geom.get("coordinates"):
            return False, "Parcel has no valid GeoJSON location. Ensure the parcel exists in the land records."
        return True, ""

    if target == S.surveyed:
        # survey report needs to exist before we can mark as surveyed (Student 3's part)
        report = db["survey_reports"].find_one({"application_id": app_id})
        if not report:
            return False, "No survey report found for this application"
        return True, ""

    if target == S.legal_review:
        # need at least one ownership document uploaded (Student 2's part)
        doc = db["application_documents"].find_one({
            "application_id": app_id,
            "document_type": {"$in": ["ownership_deed", "sale_contract"]},
            "status": {"$ne": "rejected"},
        })
        if not doc:
            return False, "Ownership documents are not uploaded"
        return True, ""

    if target == S.approved:
        if app_doc.get("status") != S.legal_review:
            return False, "Application must be in legal_review before approval"
        # All uploaded documents must be reviewed (none left pending)
        pending = db["application_documents"].find_one({
            "application_id": app_id,
            "status": "pending_review",
        })
        if pending:
            return False, (
                f"Document '{pending.get('document_name', pending.get('document_type'))}' "
                "is still pending review. All documents must be verified or rejected before approval."
            )
        # At least one ownership document must be verified
        verified_ownership = db["application_documents"].find_one({
            "application_id": app_id,
            "document_type": {"$in": ["ownership_deed", "sale_contract"]},
            "status": "verified",
        })
        if not verified_ownership:
            return False, "At least one ownership document (ownership deed or sale contract) must be verified before approval."
        return True, ""

    if target == S.certificate_issued:
        if app_doc.get("status") != S.approved:
            return False, "Application must be approved before issuing a certificate"
        return True, ""

    # on_hold, missing_documents, under_objection, rejected — no extra checks needed
    return True, ""
