from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query

from app.common.audit import log_event
from app.common.enums import ApplicationStatus as S
from app.database import get_db
from app.modules.applicants.models import (
    ApplicantCreate,
    CommentCreate,
    DocumentCreate,
    DocumentReviewRequest,
    ObjectionCreate,
)
from app.modules.applications.workflow import allowed_next, can_transition

router = APIRouter(tags=["Applicants & Portal (Student 2)"])


# ── Utilities ─────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_seq(name: str) -> int:
    result = get_db()["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return result["seq"]


def _make_applicant_id() -> str:
    return f"APP-2026-{_next_seq('applicant_id'):04d}"


def _make_document_id() -> str:
    return f"DOC-2026-{_next_seq('document_id'):04d}"


def _make_objection_id() -> str:
    return f"OBJ-2026-{_next_seq('objection_id'):04d}"


def _to_public(doc: dict | None) -> dict | None:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def _get_applicant_or_404(applicant_id: str) -> dict:
    doc = get_db()["applicants"].find_one({"applicant_id": applicant_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Applicant {applicant_id!r} not found")
    return doc


def _get_application_or_404(application_id: str) -> dict:
    doc = get_db()["land_applications"].find_one({"application_id": application_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Application {application_id!r} not found")
    return doc


# ── POST /applicants/ ─────────────────────────────────────────────────────────

@router.post("/applicants/", status_code=201)
def create_applicant(body: ApplicantCreate):
    db = get_db()

    # Enforce unique national_id
    if db["applicants"].find_one({"identity.national_id": body.identity.national_id}):
        raise HTTPException(
            status_code=409,
            detail=f"An applicant with national_id {body.identity.national_id!r} already exists",
        )

    applicant_id = body.applicant_id or _make_applicant_id()

    # Enforce unique applicant_id if caller provided one
    if db["applicants"].find_one({"applicant_id": applicant_id}):
        raise HTTPException(
            status_code=409,
            detail=f"Applicant ID {applicant_id!r} is already in use",
        )

    now = _now()
    doc = {
        "applicant_id": applicant_id,
        "full_name": body.full_name,
        "applicant_type": body.applicant_type.value,
        "verification_state": "unverified",
        "identity": {
            "national_id": body.identity.national_id,
            "verified": False,
            "verification_method": body.identity.verification_method,
            "verified_at": None,
        },
        "contacts": (
            body.contacts.model_dump()
            if body.contacts
            else {"email": None, "phone": None}
        ),
        "address": (
            body.address.model_dump()
            if body.address
            else {"city": "", "neighborhood": "", "zone_id": ""}
        ),
        "preferences": (
            body.preferences.model_dump()
            if body.preferences
            else {
                "preferred_contact": "email",
                "language": "en",
                "notifications": {
                    "on_status_change": True,
                    "on_missing_documents": True,
                    "on_certificate_ready": True,
                },
            }
        ),
        "privacy": (
            body.privacy.model_dump()
            if body.privacy
            else {"share_contact_with_staff": True, "show_in_public_registry": False}
        ),
        "stats": {
            "total_applications": 0,
            "approved_applications": 0,
            "pending_applications": 0,
        },
        "created_at": now,
        "updated_at": now,
    }

    db["applicants"].insert_one(doc)
    return _to_public(doc)


# ── GET /applicants/{applicant_id} ────────────────────────────────────────────

@router.get("/applicants/{applicant_id}")
def get_applicant(applicant_id: str):
    doc = _get_applicant_or_404(applicant_id)

    # Compute live stats from land_applications
    db = get_db()
    terminal_ok = {"approved", "certificate_issued", "closed"}
    in_progress = {"submitted", "pre_checked", "survey_required", "surveyed", "legal_review"}
    all_apps = list(db["land_applications"].find(
        {"applicant_ref.applicant_id": applicant_id}, {"status": 1}
    ))
    doc["stats"] = {
        "total_applications":   len(all_apps),
        "approved_applications": sum(1 for a in all_apps if a["status"] in terminal_ok),
        "pending_applications":  sum(1 for a in all_apps if a["status"] in in_progress),
    }

    doc.pop("privacy", None)
    return _to_public(doc)


# ── GET /applicants/{applicant_id}/applications ───────────────────────────────

@router.get("/applicants/{applicant_id}/applications")
def get_applicant_applications(
    applicant_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    _get_applicant_or_404(applicant_id)
    db = get_db()

    query = {"applicant_ref.applicant_id": applicant_id}
    total = db["land_applications"].count_documents(query)
    cursor = (
        db["land_applications"]
        .find(query)
        .sort("timestamps.submitted_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    return {
        "data": [_to_public(d) for d in cursor],
        "total": total,
        "page": page,
        "limit": limit,
    }


# ── POST /applications/{application_id}/documents ─────────────────────────────

@router.post("/applications/{application_id}/documents", status_code=201)
def upload_document(application_id: str, body: DocumentCreate):
    _get_application_or_404(application_id)
    db = get_db()

    doc_id = _make_document_id()
    now = _now()

    doc = {
        "document_id": doc_id,
        "application_id": application_id,
        "document_type": body.document_type,
        "document_name": body.document_name or body.document_type,
        "applicant_id": body.applicant_id,
        "notes": body.notes,
        "status": "pending_review",
        "uploaded_at": now,
        "reviewed_at": None,
        "reviewed_by": None,
    }

    db["application_documents"].insert_one(doc)
    log_event(
        application_id,
        "document_uploaded",
        "applicant",
        body.applicant_id or "unknown",
        {"document_type": body.document_type, "document_id": doc_id},
    )

    return _to_public(doc)


# ── POST /applications/{application_id}/comments ──────────────────────────────

@router.post("/applications/{application_id}/comments", status_code=201)
def add_comment(application_id: str, body: CommentCreate):
    _get_application_or_404(application_id)
    db = get_db()

    now = _now()
    comment = {
        "applicant_id": body.applicant_id,
        "actor_type": body.actor_type,
        "comment": body.comment,
        "posted_at": now,
    }

    db["land_applications"].update_one(
        {"application_id": application_id},
        {"$push": {"comments": comment}},
    )
    log_event(
        application_id,
        "comment_added",
        body.actor_type,
        body.applicant_id or "unknown",
        {"snippet": body.comment[:80]},
    )

    return {"message": "Comment posted", "comment": comment}


# ── POST /applications/{application_id}/objections ────────────────────────────

@router.post("/applications/{application_id}/objections", status_code=201)
def raise_objection(application_id: str, body: ObjectionCreate):
    app_doc = _get_application_or_404(application_id)
    db = get_db()

    obj_id = _make_objection_id()
    now = _now()

    objection = {
        "objection_id": obj_id,
        "application_id": application_id,
        "applicant_id": body.applicant_id,
        "reason": body.reason,
        "supporting_details": body.supporting_details,
        "status": "pending",
        "raised_at": now,
        "resolved_at": None,
        "resolution_notes": None,
    }

    db["objections"].insert_one(objection)

    # Flag the objection on the application document
    db["land_applications"].update_one(
        {"application_id": application_id},
        {
            "$set": {"objection.has_objection": True},
            "$push": {"objection.objection_ids": obj_id},
        },
    )

    # Transition to under_objection if the workflow allows it from the current state
    if can_transition(app_doc["status"], S.under_objection):
        db["land_applications"].update_one(
            {"application_id": application_id},
            {
                "$set": {
                    "status": S.under_objection.value,
                    "workflow.current_state": S.under_objection.value,
                    "workflow.allowed_next": allowed_next(S.under_objection),
                    "timestamps.updated_at": now,
                }
            },
        )

    log_event(
        application_id,
        "objection_raised",
        "applicant",
        body.applicant_id or "unknown",
        {"objection_id": obj_id, "reason_snippet": body.reason[:80]},
    )

    return _to_public(objection)


# ── GET /applications/{application_id}/timeline ───────────────────────────────

@router.get("/applications/{application_id}/timeline")
def get_timeline(
    application_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
):
    _get_application_or_404(application_id)
    db = get_db()

    log_doc = db["performance_logs"].find_one({"application_id": application_id})
    events = (log_doc or {}).get("events", [])

    total = len(events)
    start = (page - 1) * limit
    page_events = events[start: start + limit]

    return {
        "data": page_events,
        "total": total,
        "page": page,
        "limit": limit,
    }


# ── PATCH /applications/{application_id}/documents/{document_id}/review ──────
# Registrar accepts or rejects an uploaded document.

@router.patch("/applications/{application_id}/documents/{document_id}/review")
def review_document(
    application_id: str,
    document_id: str,
    body: DocumentReviewRequest,
):
    _get_application_or_404(application_id)
    db = get_db()

    doc = db["application_documents"].find_one({
        "document_id": document_id,
        "application_id": application_id,
    })
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document {document_id!r} not found for application {application_id!r}",
        )

    now = _now()
    db["application_documents"].update_one(
        {"document_id": document_id},
        {
            "$set": {
                "status":      body.status,
                "reviewed_at": now,
                "reviewed_by": body.reviewer_id,
                "review_notes": body.review_notes,
            }
        },
    )
    log_event(
        application_id,
        f"document_{body.status}",
        "registrar",
        body.reviewer_id,
        {"document_id": document_id, "notes": body.review_notes},
    )

    updated = db["application_documents"].find_one({"document_id": document_id})
    return _to_public(updated)


# ── GET /parcels/{parcel_code} ────────────────────────────────────────────────
# Returns a parcel with its GeoJSON geometry (used by the Registrar map view).

@router.get("/parcels/{parcel_code}")
def get_parcel(parcel_code: str):
    doc = get_db()["parcels"].find_one({"parcel_code": parcel_code})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Parcel {parcel_code!r} not found",
        )
    return _to_public(doc)


# ── GET /applications/{application_id}/certificate-status ────────────────────
# Returns the issued certificate for an application, or null if none yet.

@router.get("/applications/{application_id}/certificate-status")
def get_certificate_status(application_id: str):
    _get_application_or_404(application_id)
    doc = get_db()["certificates"].find_one({"application_id": application_id})
    if not doc:
        return {"certificate": None, "message": "No certificate issued yet"}
    return {"certificate": _to_public(doc)}
