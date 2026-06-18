"""Database helpers for the Land Application module (Student 1).
Uses only PyMongo + stdlib. No external libraries."""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.common.enums import ApplicationStatus as S
from app.database import get_db
from app.modules.applications.workflow import allowed_next

# Which timestamp field to stamp when ENTERING each state.
TIMESTAMP_FIELD = {
    S.submitted: "submitted_at",
    S.pre_checked: "pre_checked_at",
    S.survey_required: "survey_required_at",
    S.surveyed: "surveyed_at",
    S.legal_review: "legal_review_at",
    S.approved: "approved_at",
    S.certificate_issued: "certificate_issued_at",
    S.closed: "closed_at",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def next_sequence(name: str) -> int:
    """Atomic counter -> sequential readable IDs (LRMIS-2026-0001, ...)."""
    c = get_db()["counters"].find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    return c["seq"]


def make_application_id() -> str:
    return f"LRMIS-2026-{next_sequence('application_id'):04d}"


def make_certificate_id() -> str:
    return f"CERT-2026-{next_sequence('certificate_id'):04d}"


def to_public(doc: dict | None) -> dict | None:
    """Turn Mongo _id (ObjectId) into a JSON-safe string field 'id'."""
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def get_application_or_404(app_id: str) -> dict:
    doc = get_db()["land_applications"].find_one({"application_id": app_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Application {app_id} not found")
    return doc


def set_state(app_id: str, target: str, extra: dict | None = None) -> None:
    """Update status + workflow block + the matching timestamp."""
    target = target.value if hasattr(target, "value") else target
    changes = {
        "status": target,
        "workflow.current_state": target,
        "workflow.allowed_next": allowed_next(target),
        "timestamps.updated_at": now(),
    }
    field = TIMESTAMP_FIELD.get(target)
    if field:
        changes[f"timestamps.{field}"] = now()
    if extra:
        changes.update(extra)
    get_db()["land_applications"].update_one(
        {"application_id": app_id}, {"$set": changes}
    )