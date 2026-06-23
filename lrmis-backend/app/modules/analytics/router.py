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
            "phone": body.phone,
        },
        "coverage_zones": body.coverage_zones,
        "skills": body.skills,
        "schedule": schedule,
        "workload": {
            "current_tasks": 0,
            "max_tasks": schedule["max_concurrent_tasks"],
        },
        "performance": {
            "total_tasks_completed": 0,
            "avg_completion_days": None,
            "on_time_rate": None,
        },
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }

    db["staff_members"].insert_one(doc)
    return _to_public(doc)


# ── GET /staff/{staff_id} ──────────────────────────────────────────────────────

@router.get("/staff/{staff_id}")
def get_staff(staff_id: str):
    doc = _get_staff_or_404(staff_id)
    db = get_db()

    # compute live workload from survey_tasks
    active_milestones = [
        SurveyMilestone.assigned.value,
        SurveyMilestone.visit_scheduled.value,
        SurveyMilestone.arrived_on_site.value,
        SurveyMilestone.survey_started.value,
        SurveyMilestone.survey_completed.value,
    ]
    current_tasks = db["survey_tasks"].count_documents({
        "assigned_to": staff_id,
        "milestone": {"$in": active_milestones},
    })
    completed_tasks = db["survey_tasks"].count_documents({
        "assigned_to": staff_id,
        "milestone": SurveyMilestone.registrar_reviewed.value,
    })
    doc["workload"]["current_tasks"] = current_tasks
    doc["performance"]["total_tasks_completed"] = completed_tasks

    return _to_public(doc)


# ── POST /applications/{application_id}/auto-assign-surveyor ───────────────────

@router.post("/applications/{application_id}/auto-assign-surveyor", status_code=201)
def auto_assign_surveyor(application_id: str):
    app_doc = _get_application_or_404(application_id)
    db = get_db()

    # only makes sense to assign from pre_checked or survey_required
    allowed_from = {S.pre_checked.value, S.survey_required.value}
    if app_doc["status"] not in allowed_from:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot assign surveyor when status is {app_doc['status']!r}. "
                   "Must be pre_checked or survey_required.",
        )

    # bail if a task already exists for this application
    if db["survey_tasks"].find_one({"application_id": application_id}):
        raise HTTPException(
            status_code=409,
            detail="A survey task already exists for this application",
        )

    zone_id = (app_doc.get("parcel_ref") or {}).get("zone_id", "")
    app_type = app_doc.get("application_type", "")

    candidates = list(db["staff_members"].find({"role": "surveyor", "is_active": True}))
    if not candidates:
        raise HTTPException(status_code=422, detail="No active surveyors found in the system")

    active_milestones = [
        SurveyMilestone.assigned.value,
        SurveyMilestone.visit_scheduled.value,
        SurveyMilestone.arrived_on_site.value,
        SurveyMilestone.survey_started.value,
        SurveyMilestone.survey_completed.value,
    ]

    def _score(s: dict) -> tuple:
        workload = db["survey_tasks"].count_documents({
            "assigned_to": s["staff_id"],
            "milestone": {"$in": active_milestones},
        })
        max_tasks = s.get("schedule", {}).get("max_concurrent_tasks", 3)
        is_available = workload < max_tasks
        zone_match = zone_id in s.get("coverage_zones", [])
        # prefer available → zone-matched → lowest workload
        return (0 if is_available else 1, 0 if zone_match else 1, workload)

    candidates.sort(key=_score)
    chosen = candidates[0]

    task_id = _make_task_id()
    now = _now()

    task = {
        "task_id": task_id,
        "application_id": application_id,
        "assigned_to": chosen["staff_id"],
        "surveyor_name": chosen["full_name"],
        "zone_id": zone_id,
        "application_type": app_type,
        "parcel_number": (app_doc.get("parcel_ref") or {}).get("parcel_number", ""),
        "milestone": SurveyMilestone.assigned.value,
        "priority": "normal",
        "scheduled_date": None,
        "field_notes": [],
        "created_at": now,
        "updated_at": now,
    }
    db["survey_tasks"].insert_one(task)

    # increment workload counter on the chosen surveyor
    db["staff_members"].update_one(
        {"staff_id": chosen["staff_id"]},
        {"$inc": {"workload.current_tasks": 1}, "$set": {"updated_at": now}},
    )

    # advance to survey_required if application is still in pre_checked
    if app_doc["status"] == S.pre_checked.value and can_transition(app_doc["status"], S.survey_required):
        db["land_applications"].update_one(
            {"application_id": application_id},
            {
                "$set": {
                    "status": S.survey_required.value,
                    "workflow.current_state": S.survey_required.value,
                    "workflow.allowed_next": allowed_next(S.survey_required),
                    "timestamps.survey_required_at": now,
                    "timestamps.updated_at": now,
                }
            },
        )

    log_event(
        application_id,
        "surveyor_assigned",
        "system",
        "auto-assign",
        {"task_id": task_id, "assigned_to": chosen["staff_id"], "zone_id": zone_id},
    )

    return _to_public(task)


# ── PATCH /applications/{application_id}/survey-milestone ─────────────────────

@router.patch("/applications/{application_id}/survey-milestone")
def update_survey_milestone(application_id: str, body: SurveyMilestoneRequest):
    _get_application_or_404(application_id)
    db = get_db()

    task = db["survey_tasks"].find_one({"application_id": application_id})
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"No survey task found for application {application_id!r}. "
                   "Run auto-assign-surveyor first.",
        )

    if task["assigned_to"] != body.surveyor_id:
        raise HTTPException(
            status_code=403,
            detail=f"Surveyor {body.surveyor_id!r} is not assigned to this task",
        )

    # milestones must advance forward
    milestone_order = [m.value for m in SurveyMilestone]
    current_idx = milestone_order.index(task["milestone"])
    new_idx = milestone_order.index(body.milestone.value)
    if new_idx <= current_idx:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot go from {task['milestone']!r} to {body.milestone.value!r}. "
                   "Milestones must advance forward.",
        )

    now = _now()
    update_fields: dict = {"milestone": body.milestone.value, "updated_at": now}
    if body.scheduled_date and body.milestone == SurveyMilestone.visit_scheduled:
        update_fields["scheduled_date"] = body.scheduled_date

    db["survey_tasks"].update_one({"application_id": application_id}, {"$set": update_fields})

    if body.notes:
        db["survey_tasks"].update_one(
            {"application_id": application_id},
            {"$push": {"field_notes": {"note": body.notes, "at": now, "by": body.surveyor_id}}},
        )

    log_event(
        application_id,
        f"survey_milestone_{body.milestone.value}",
        "surveyor",
        body.surveyor_id,
        {"milestone": body.milestone.value, "notes": body.notes},
    )

    updated = db["survey_tasks"].find_one({"application_id": application_id})
    return _to_public(updated)


# ── POST /applications/{application_id}/survey-report ─────────────────────────
# Critical: writes to survey_reports which unblocks survey_required → surveyed.

@router.post("/applications/{application_id}/survey-report", status_code=201)
def upload_survey_report(application_id: str, body: SurveyReportCreate):
    _get_application_or_404(application_id)
    db = get_db()

    task = db["survey_tasks"].find_one({"application_id": application_id})
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"No survey task found for application {application_id!r}. "
                   "A surveyor must be assigned before a report can be submitted.",
        )

    if task["assigned_to"] != body.surveyor_id:
        raise HTTPException(
            status_code=403,
            detail=f"Surveyor {body.surveyor_id!r} is not assigned to this task",
        )

    if db["survey_reports"].find_one({"application_id": application_id}):
        raise HTTPException(
            status_code=409,
            detail=f"A survey report already exists for application {application_id!r}",
        )

    report_id = _make_report_id()
    now = _now()

    report = {
        "report_id": report_id,
        "application_id": application_id,
        "task_id": task["task_id"],
        "surveyor_id": body.surveyor_id,
        "findings": body.findings,
        "parcel_area_sqm": body.parcel_area_sqm,
        "boundary_confirmed": body.boundary_confirmed,
        "coordinates_verified": body.coordinates_verified,
        "field_notes": body.field_notes,
        "recommendations": body.recommendations,
        "registrar_review": None,
        "submitted_at": now,
    }
    db["survey_reports"].insert_one(report)

    # milestone advances to report_uploaded so the registrar can see it
    db["survey_tasks"].update_one(
        {"application_id": application_id},
        {"$set": {"milestone": SurveyMilestone.report_uploaded.value, "updated_at": now}},
    )

    # decrement active workload on the surveyor
    db["staff_members"].update_one(
        {"staff_id": body.surveyor_id},
        {
            "$inc": {"workload.current_tasks": -1, "performance.total_tasks_completed": 1},
            "$set": {"updated_at": now},
        },
    )

    log_event(
        application_id,
        "survey_report_uploaded",
        "surveyor",
        body.surveyor_id,
        {"report_id": report_id, "boundary_confirmed": body.boundary_confirmed},
    )

    return _to_public(report)


# ── PATCH /applications/{application_id}/registrar-review ─────────────────────

@router.patch("/applications/{application_id}/registrar-review")
def registrar_review(application_id: str, body: RegistrarReviewRequest):
    _get_application_or_404(application_id)
    db = get_db()

    report = db["survey_reports"].find_one({"application_id": application_id})
    if not report:
        raise HTTPException(
            status_code=422,
            detail=f"No survey report found for application {application_id!r}. "
                   "Submit a survey report before the registrar can review it.",
        )

    now = _now()

    db["survey_reports"].update_one(
        {"application_id": application_id},
        {
            "$set": {
                "registrar_review": {
                    "registrar_id": body.registrar_id,
                    "decision": body.decision,
                    "notes": body.notes,
                    "reviewed_at": now,
                }
            }
        },
    )

    db["survey_tasks"].update_one(
        {"application_id": application_id},
        {"$set": {"milestone": SurveyMilestone.registrar_reviewed.value, "updated_at": now}},
    )

    log_event(
        application_id,
        f"registrar_survey_review_{body.decision}",
        "registrar",
        body.registrar_id,
        {"decision": body.decision, "notes": body.notes},
    )

    updated = db["survey_reports"].find_one({"application_id": application_id})
    return _to_public(updated)