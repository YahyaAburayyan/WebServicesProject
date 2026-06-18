from fastapi import APIRouter, Header, HTTPException, Query

from app.common.audit import log_event
from app.common.enums import ApplicationStatus as S
from app.database import get_db
from app.modules.applications import service as svc
from app.modules.applications.models import (
    ApplicationCreate,
    CertificateRequest,
    HoldRequest,
    RejectRequest,
    TransitionRequest,
)
from app.modules.applications.workflow import allowed_next, can_transition, guard

router = APIRouter(prefix="/applications", tags=["Applications (Student 1)"])

# POST /applications/
@router.post("/", status_code=201)
def create_application(
    body: ApplicationCreate,
    idempotency_key: str | None = Header(default=None),
):
    apps = get_db()["land_applications"]

    # if the client sends the same idempotency key twice, return the original instead of creating a duplicate
    if idempotency_key:
        existing = apps.find_one({"idempotency_key": idempotency_key})
        if existing:
            return svc.to_public(existing)

    app_id = svc.make_application_id()

    doc = {
        "application_id": app_id,
        "application_type": body.application_type.value,
        "status": S.submitted.value,
        "priority": body.priority,
        "applicant_ref": body.applicant_ref.model_dump(),
        "parcel_ref": body.parcel_ref.model_dump(),
        "description": body.description,
        "tags": body.tags,
        "workflow": {
            "current_state": S.submitted.value,
            "allowed_next": allowed_next(S.submitted),
            "transition_rules_version": "v1.0",
        },
        "required_documents": [],
        "timestamps": {
            "submitted_at": svc.now(),
            "pre_checked_at": None,
            "survey_required_at": None,
            "surveyed_at": None,
            "legal_review_at": None,
            "approved_at": None,
            "certificate_issued_at": None,
            "closed_at": None,
            "updated_at": svc.now(),
        },
        "assignment": {
            "assigned_surveyor_id": None,
            "assigned_registrar_id": None,
        },
        "objection": {
            "has_objection": False,
            "objection_ids": [],
        },
        "internal": {
            "notes": [],
            "visibility": "staff_only",
        },
    }

    # only save the key to the document if one was actually sent
    # we can't store null here because the sparse-unique index on idempotency_key
    # would treat null as a real value and block future inserts
    if idempotency_key:
        doc["idempotency_key"] = idempotency_key

    apps.insert_one(doc)
    log_event(app_id, "submitted", body.applicant_ref.applicant_type,
              body.applicant_ref.applicant_id, {"channel": "web"})

    return svc.to_public(doc)

# GET /applications/{id}
@router.get("/{application_id}")
def get_application(application_id: str):
    return svc.to_public(svc.get_application_or_404(application_id))

# GET /applications/
@router.get("/")
def list_applications(
    status: str | None = None,
    application_type: str | None = None,
    zone_id: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    apps = get_db()["land_applications"]
    query: dict = {}

    if status:
        query["status"] = status
    if application_type:
        query["application_type"] = application_type
    if zone_id:
        query["parcel_ref.zone_id"] = zone_id

    total = apps.count_documents(query)
    cursor = (
        apps.find(query)
        .sort("timestamps.submitted_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    return {
        "data": [svc.to_public(d) for d in cursor],
        "total": total,
        "page": page,
        "limit": limit,
    }

# PATCH /applications/{id}/transition
@router.patch("/{application_id}/transition")
def transition(application_id: str, body: TransitionRequest):
    app_doc = svc.get_application_or_404(application_id)
    current = app_doc["status"]
    target = body.target_state.value

    if not can_transition(current, target):
        raise HTTPException(
            status_code=409,
            detail=f"Illegal transition: {current} -> {target}"
        )

    ok, reason = guard(app_doc, target)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    svc.set_state(application_id, target)
    log_event(application_id, target, body.actor_type, body.actor_id, {"note": body.note})

    return svc.to_public(svc.get_application_or_404(application_id))

# POST /applications/{id}/hold
@router.post("/{application_id}/hold")
def hold(application_id: str, body: HoldRequest):
    app_doc = svc.get_application_or_404(application_id)

    if not can_transition(app_doc["status"], S.on_hold):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot hold from state {app_doc['status']}"
        )

    svc.set_state(application_id, S.on_hold, {"internal.hold_reason": body.reason})
    log_event(application_id, "on_hold", body.actor_type, body.actor_id, {"reason": body.reason})

    return svc.to_public(svc.get_application_or_404(application_id))

# POST /applications/{id}/reject
@router.post("/{application_id}/reject")
def reject(application_id: str, body: RejectRequest):
    app_doc = svc.get_application_or_404(application_id)

    if not can_transition(app_doc["status"], S.rejected):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject from state {app_doc['status']}"
        )

    svc.set_state(application_id, S.rejected, {"internal.rejection_reason": body.reason})
    log_event(application_id, "rejected", body.actor_type, body.actor_id, {"reason": body.reason})

    return svc.to_public(svc.get_application_or_404(application_id))

# POST /applications/{id}/certificate	
@router.post("/{application_id}/certificate", status_code=201)
def issue_certificate(application_id: str, body: CertificateRequest):
    app_doc = svc.get_application_or_404(application_id)

    if app_doc["status"] != S.approved:
        raise HTTPException(
            status_code=409,
            detail="Certificate cannot be issued unless the application is approved"
        )

    cert_id = svc.make_certificate_id()

    cert = {
        "certificate_id": cert_id,
        "application_id": application_id,
        "parcel_id": (app_doc.get("parcel_ref") or {}).get("parcel_id"),
        "certificate_type": body.certificate_type,
        "status": "issued",
        "issued_to": app_doc.get("applicant_ref"),
        "issued_at": svc.now(),
        "issued_by": body.issued_by,
        "verification": {
            "qr_code_url": f"/certificates/{cert_id}/verify",
            "digital_signature_stub": "signed_hash_example",
        },
    }

    get_db()["certificates"].insert_one(cert)
    svc.set_state(application_id, S.certificate_issued)
    log_event(application_id, "certificate_issued", "registrar", body.issued_by,
              {"certificate_id": cert_id})

    return svc.to_public(cert)
