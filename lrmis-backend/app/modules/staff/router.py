from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.common.audit import log_event
from app.common.enums import ApplicationStatus as S, SurveyMilestone
from app.database import get_db
from app.modules.applications.workflow import allowed_next, can_transition
from app.modules.staff.models import (
    RegistrarReviewRequest,
    StaffCreate,
    SurveyMilestoneRequest,
    SurveyReportCreate,
)

router = APIRouter(tags=["Staff, Survey & Assignment (Student 3)"])


# ── Utilities ──────────────────────────────────────────────────────────────────

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


def _make_staff_id() -> str:
    return f"STAF-2026-{_next_seq('staff_id'):04d}"


def _make_report_id() -> str:
    return f"RPT-2026-{_next_seq('report_id'):04d}"


def _make_task_id() -> str:
    return f"TASK-2026-{_next_seq('task_id'):04d}"


def _to_public(doc: dict | None) -> dict | None:
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


def _get_application_or_404(application_id: str) -> dict:
    doc = get_db()["land_applications"].find_one({"application_id": application_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Application {application_id!r} not found")
    return doc


def _get_staff_or_404(staff_id: str) -> dict:
    doc = get_db()["staff_members"].find_one({"staff_id": staff_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Staff member {staff_id!r} not found")
    return doc


# ── POST /staff/ ───────────────────────────────────────────────────────────────

@router.post("/staff/", status_code=201)
def create_staff(body: StaffCreate):
    db = get_db()

    # national_id must be unique across all staff members
    if db["staff_members"].find_one({"national_id": body.national_id}):
        raise HTTPException(
            status_code=409,
            detail=f"A staff member with national_id {body.national_id!r} already exists",
        )

    staff_id = _make_staff_id()
    now = _now()

    schedule = (
        body.schedule.model_dump()
        if body.schedule
        else {
            "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "shift_start": "08:00",
            "shift_end": "16:00",
            "max_concurrent_tasks": 3,
        }
    )

    doc = {
        "staff_id": staff_id,
        "full_name": body.full_name,
        "role": body.role.value,
        "national_id": body.national_id,
        "contacts": {
            "email": body.email,
... (333 lines left)