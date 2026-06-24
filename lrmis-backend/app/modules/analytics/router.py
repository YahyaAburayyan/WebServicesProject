import csv
import io
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.common.audit import log_event
from app.common.enums import ApplicationStatus as S, SurveyMilestone
from app.database import get_db
from app.modules.applications.workflow import allowed_next, can_transition
from app.modules.staff.models import (
    ReassignRequest,
    RegistrarReviewRequest,
    StaffCreate,
    SurveyMilestoneRequest,
    SurveyReportCreate,
)

router = APIRouter(tags=["Staff, Survey & Assignment (Student 3)"])

# ── Simple in-memory TTL cache for heavy analytics queries ─────────────────────
_cache: dict = {}
_CACHE_TTL = 60  # seconds

def _get_cached(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None

def _set_cached(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}
    return data


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


# ── GET /staff/ ───────────────────────────────────────────────────────────────

@router.get("/staff/")
def list_staff(role: str | None = None, limit: int = 100):
    db = get_db()
    query: dict = {}
    if role:
        query["role"] = role
    docs = list(db["staff_members"].find(query, {"_id": 0}).limit(limit))
    for d in docs:
        d.pop("password_hash", None)
    return {"items": docs, "total": len(docs)}


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


# ── GET /staff/{staff_id}/tasks ─────────────────────────────────────────────────

@router.get("/staff/{staff_id}/tasks")
def get_staff_tasks(staff_id: str, status: str | None = None):
    _get_staff_or_404(staff_id)
    db = get_db()
    query: dict = {"assigned_to": staff_id}
    if status == "active":
        query["milestone"] = {"$nin": [SurveyMilestone.registrar_reviewed.value]}
    elif status == "completed":
        query["milestone"] = SurveyMilestone.registrar_reviewed.value
    tasks = list(db["survey_tasks"].find(query).sort("assigned_at", -1))
    return {"data": [_to_public(t) for t in tasks], "total": len(tasks)}


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


# ── POST /applications/{application_id}/reassign-surveyor ─────────────────────
# Manual reassignment: moves an existing task to a different surveyor.

@router.post("/applications/{application_id}/reassign-surveyor")
def reassign_surveyor(application_id: str, body: ReassignRequest):
    _get_application_or_404(application_id)
    db = get_db()

    new_surveyor = _get_staff_or_404(body.surveyor_id)
    if new_surveyor.get("role") != "surveyor":
        raise HTTPException(status_code=422, detail="Target staff member is not a surveyor")

    task = db["survey_tasks"].find_one({"application_id": application_id})
    if not task:
        raise HTTPException(
            status_code=404,
            detail="No survey task found — run auto-assign-surveyor first",
        )

    old_id = task["assigned_to"]
    if old_id == body.surveyor_id:
        raise HTTPException(status_code=409, detail="This surveyor is already assigned to the task")

    now = _now()
    db["survey_tasks"].update_one(
        {"application_id": application_id},
        {"$set": {
            "assigned_to": body.surveyor_id,
            "surveyor_name": new_surveyor.get("full_name", body.surveyor_id),
            "updated_at": now,
        }},
    )

    # Adjust workload counters
    db["staff_members"].update_one(
        {"staff_id": old_id},
        {"$inc": {"workload.current_tasks": -1}, "$set": {"updated_at": now}},
    )
    db["staff_members"].update_one(
        {"staff_id": body.surveyor_id},
        {"$inc": {"workload.current_tasks": 1}, "$set": {"updated_at": now}},
    )

    log_event(
        application_id,
        "surveyor_reassigned",
        "registrar",
        "system",
        {"from": old_id, "to": body.surveyor_id, "reason": body.reason},
    )

    updated = db["survey_tasks"].find_one({"application_id": application_id})
    return _to_public(updated)


# ── GET /applications/{application_id}/survey-task ────────────────────────────

@router.get("/applications/{application_id}/survey-task")
def get_survey_task(application_id: str):
    _get_application_or_404(application_id)
    db = get_db()
    task = db["survey_tasks"].find_one({"application_id": application_id})
    if not task:
        raise HTTPException(status_code=404, detail=f"No survey task for {application_id!r}")
    result = _to_public(task)
    surveyor = db["staff_members"].find_one({"staff_id": task["assigned_to"]}, {"_id": 0})
    result["surveyor_name"] = (surveyor or {}).get("full_name", task["assigned_to"])
    return result


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


# ── GET /applications/{application_id}/survey-report ──────────────────────────

@router.get("/applications/{application_id}/survey-report")
def get_survey_report(application_id: str):
    _get_application_or_404(application_id)
    doc = get_db()["survey_reports"].find_one({"application_id": application_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"No survey report for {application_id!r}")
    return _to_public(doc)


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


# ════════════════════════════════════════════════════════════════════════════════
# Analytics Endpoints (Student 3)
# ════════════════════════════════════════════════════════════════════════════════

# ── GET /analytics/kpis ─────────────────────────────────────────────────────────

@router.get("/analytics/kpis")
def analytics_kpis():
    cached = _get_cached("kpis")
    if cached is not None:
        return cached
    db = get_db()
    apps = db["land_applications"]
    total = apps.count_documents({})
    pending_statuses = [
        S.submitted.value, S.pre_checked.value,
        S.survey_required.value, S.surveyed.value, S.legal_review.value,
        S.on_hold.value, S.missing_documents.value,
    ]
    approved = apps.count_documents({"status": S.approved.value})
    pending_review = apps.count_documents({"status": {"$in": pending_statuses}})
    closed = apps.count_documents({"status": {"$in": [S.certificate_issued.value, S.closed.value]}})
    rejected = apps.count_documents({"status": S.rejected.value})
    under_objection = apps.count_documents({"status": S.under_objection.value})

    # avg processing days (submitted → approved) via aggregation
    avg_pipeline = [
        {"$match": {"status": S.approved.value,
                    "timestamps.submitted_at": {"$exists": True},
                    "timestamps.approved_at": {"$exists": True}}},
        {"$project": {"days": {"$divide": [
            {"$subtract": ["$timestamps.approved_at", "$timestamps.submitted_at"]},
            86_400_000,
        ]}}},
        {"$group": {"_id": None, "avg": {"$avg": "$days"}}},
    ]
    result = list(apps.aggregate(avg_pipeline))
    avg_days = round(result[0]["avg"], 1) if result else None

    # delayed applications: pending for more than 14 days
    from datetime import timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - __import__('datetime').timedelta(days=14)
    delayed = apps.count_documents({
        "status": {"$in": pending_statuses},
        "timestamps.submitted_at": {"$lt": cutoff},
    })

    # certificates issued this calendar month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    certs_this_month = db["certificates"].count_documents({
        "issued_at": {"$gte": month_start},
    })

    payload = {
        "total_applications": total,
        "pending_review": pending_review,
        "approved": approved,
        "closed": closed,
        "rejected": rejected,
        "under_objection": under_objection,
        "avg_processing_days": avg_days,
        "delayed_applications": delayed,
        "certificates_this_month": certs_this_month,
    }
    return _set_cached("kpis", payload)


# ── GET /analytics/status-breakdown ────────────────────────────────────────────

@router.get("/analytics/status-breakdown")
def analytics_status_breakdown():
    db = get_db()
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "status": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    return {"data": list(db["land_applications"].aggregate(pipeline))}


# ── GET /analytics/application-trends ─────────────────────────────────────────

@router.get("/analytics/application-trends")
def analytics_application_trends(period: str = "monthly", limit: int = 12):
    db = get_db()
    fmt = "%Y-%m" if period == "monthly" else "%Y-%W"
    pipeline = [
        {"$match": {"timestamps.submitted_at": {"$exists": True}}},
        {"$project": {"period": {"$dateToString": {"format": fmt, "date": "$timestamps.submitted_at"}}}},
        {"$group": {"_id": "$period", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "period": "$_id", "count": 1}},
    ]
    return {"data": list(db["land_applications"].aggregate(pipeline))}


# ── GET /analytics/zone-heatmap ────────────────────────────────────────────────

@router.get("/analytics/zone-heatmap")
def analytics_zone_heatmap():
    db = get_db()
    pipeline = [
        {"$match": {"parcel_ref.zone_id": {"$exists": True}}},
        {"$group": {"_id": "$parcel_ref.zone_id", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "zone_id": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]
    return {"data": list(db["land_applications"].aggregate(pipeline))}


# ── GET /analytics/staff-workload ──────────────────────────────────────────────

@router.get("/analytics/staff-workload")
def analytics_staff_workload():
    db = get_db()
    active_milestones = [
        SurveyMilestone.assigned.value,
        SurveyMilestone.visit_scheduled.value,
        SurveyMilestone.arrived_on_site.value,
        SurveyMilestone.survey_started.value,
        SurveyMilestone.survey_completed.value,
    ]
    staff = list(db["staff_members"].find({"role": "surveyor", "is_active": True}))
    result = []
    for s in staff:
        sid = s["staff_id"]
        active = db["survey_tasks"].count_documents(
            {"assigned_to": sid, "milestone": {"$in": active_milestones}}
        )
        result.append({
            "staff_id": sid,
            "name": s.get("full_name", ""),
            "active_tasks": active,
            "max_tasks": s.get("schedule", {}).get("max_concurrent_tasks", 3),
        })
    result.sort(key=lambda x: x["active_tasks"], reverse=True)
    return {"data": result}


# ── GET /analytics/processing-times ────────────────────────────────────────────

@router.get("/analytics/processing-times")
def analytics_processing_times():
    db = get_db()
    pipeline = [
        {"$match": {
            "timestamps.submitted_at": {"$exists": True},
            "timestamps.approved_at": {"$exists": True},
        }},
        {"$project": {"days": {"$divide": [
            {"$subtract": ["$timestamps.approved_at", "$timestamps.submitted_at"]},
            86_400_000,
        ]}, "type": "$application_type"}},
        {"$group": {
            "_id": None,
            "avg_total_days": {"$avg": "$days"},
            "min_days": {"$min": "$days"},
            "max_days": {"$max": "$days"},
        }},
        {"$project": {"_id": 0, "avg_total_days": {"$round": ["$avg_total_days", 1]},
                      "min_days": {"$round": ["$min_days", 1]},
                      "max_days": {"$round": ["$max_days", 1]}}},
    ]
    result = list(db["land_applications"].aggregate(pipeline))
    return result[0] if result else {"avg_total_days": None, "min_days": None, "max_days": None}


# ── GET /analytics/geofeeds/parcels ────────────────────────────────────────────

@router.get("/analytics/geofeeds/parcels")
def geofeed_parcels():
    db = get_db()
    parcels = list(db["parcels"].find({}))
    features = []
    for p in parcels:
        geom = p.pop("geometry", None)
        _to_public(p)
        if geom:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "parcel_number": p.get("parcel_number", ""),
                    "zone_id": p.get("zone_id", ""),
                    "area_sqm": p.get("area_sqm"),
                    "status": p.get("status", ""),
                },
            })
    return {"type": "FeatureCollection", "features": features}


# ── GET /analytics/geofeeds/pending-heatmap ───────────────────────────────────

@router.get("/analytics/geofeeds/pending-heatmap")
def geofeed_pending_heatmap():
    db = get_db()
    pending_statuses = [
        S.submitted.value, S.pre_checked.value,
        S.survey_required.value, S.surveyed.value, S.legal_review.value,
    ]
    pending_apps = list(db["land_applications"].find(
        {"status": {"$in": pending_statuses}, "parcel_ref.parcel_number": {"$exists": True}},
        {"parcel_ref": 1},
    ))

    # count pending apps per parcel
    parcel_counts: dict[str, int] = {}
    for app in pending_apps:
        pn = (app.get("parcel_ref") or {}).get("parcel_number", "")
        if pn:
            parcel_counts[pn] = parcel_counts.get(pn, 0) + 1

    # fetch matching parcels with geometry
    features = []
    for pn, count in parcel_counts.items():
        parcel = db["parcels"].find_one({"parcel_number": pn})
        if not parcel:
            continue
        geom = parcel.get("geometry")
        if not geom:
            continue
        # compute centroid from outer ring of polygon
        if geom.get("type") == "Polygon" and geom.get("coordinates"):
            ring = geom["coordinates"][0]
            lng = sum(c[0] for c in ring) / len(ring)
            lat = sum(c[1] for c in ring) / len(ring)
            centroid = {"type": "Point", "coordinates": [lng, lat]}
        elif geom.get("type") == "Point":
            centroid = geom
        else:
            continue
        features.append({
            "type": "Feature",
            "geometry": centroid,
            "properties": {"parcel_number": pn, "application_count": count},
        })

    return {"type": "FeatureCollection", "features": features}


# ════════════════════════════════════════════════════════════════════════════════
# Spec-Required Endpoint Names (exact names from project specification PDF)
# Also demonstrates required MongoDB operators: $facet, $unwind, $bucketAuto,
# $lookup, $geoNear — in addition to $group/$match/$sort/$project already used
# ════════════════════════════════════════════════════════════════════════════════


# ── GET /analytics/applications-by-status ─────────────────────────────────────
# Uses $facet: multi-category analytics in a single aggregation round-trip

@router.get("/analytics/applications-by-status")
def analytics_applications_by_status():
    cached = _get_cached("by_status")
    if cached is not None:
        return cached
    db = get_db()
    pipeline = [
        {
            "$facet": {
                "by_status": [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    {"$project": {"_id": 0, "status": "$_id", "count": 1}},
                    {"$sort": {"count": -1}},
                ],
                "by_type": [
                    {"$group": {"_id": "$application_type", "count": {"$sum": 1}}},
                    {"$project": {"_id": 0, "application_type": "$_id", "count": 1}},
                    {"$sort": {"count": -1}},
                ],
                "totals": [
                    {"$count": "total"},
                ],
            }
        }
    ]
    result = list(db["land_applications"].aggregate(pipeline))
    if not result:
        return _set_cached("by_status", {"by_status": [], "by_type": [], "total": 0})
    r = result[0]
    payload = {
        "by_status": r.get("by_status", []),
        "by_type": r.get("by_type", []),
        "total": r["totals"][0]["total"] if r.get("totals") else 0,
    }
    return _set_cached("by_status", payload)


# ── GET /analytics/applications-by-zone ───────────────────────────────────────
# Uses $facet for parallel aggregations + $unwind to flatten coverage_zones

@router.get("/analytics/applications-by-zone")
def analytics_applications_by_zone():
    db = get_db()
    pending_statuses = [
        S.submitted.value, S.pre_checked.value,
        S.survey_required.value, S.surveyed.value, S.legal_review.value,
    ]
    app_pipeline = [
        {
            "$facet": {
                "by_zone": [
                    {"$match": {"parcel_ref.zone_id": {"$exists": True, "$regex": "^ZONE-", "$options": "i"}}},
                    {"$group": {
                        "_id": "$parcel_ref.zone_id",
                        "count": {"$sum": 1},
                        "pending": {"$sum": {"$cond": [{"$in": ["$status", pending_statuses]}, 1, 0]}},
                        "approved": {"$sum": {"$cond": [{"$eq": ["$status", S.approved.value]}, 1, 0]}},
                    }},
                    {"$project": {"_id": 0, "zone_id": "$_id", "count": 1, "pending": 1, "approved": 1}},
                    {"$sort": {"count": -1}},
                ],
                "by_city": [
                    {"$match": {"location.city": {"$exists": True, "$ne": ""}}},
                    {"$group": {"_id": "$location.city", "count": {"$sum": 1}}},
                    {"$project": {"_id": 0, "city": "$_id", "count": 1}},
                    {"$sort": {"count": -1}},
                    {"$limit": 10},
                ],
            }
        }
    ]
    # $unwind flattens each surveyor's coverage_zones array for per-zone counts
    staff_pipeline = [
        {"$match": {"role": "surveyor", "is_active": True, "coverage_zones": {"$exists": True, "$ne": []}}},
        {"$unwind": "$coverage_zones"},
        {"$group": {"_id": "$coverage_zones", "surveyor_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "zone_id": "$_id", "surveyor_count": 1}},
    ]
    apps = list(db["land_applications"].aggregate(app_pipeline))
    staff_by_zone = list(db["staff_members"].aggregate(staff_pipeline))
    surveyor_map = {s["zone_id"]: s["surveyor_count"] for s in staff_by_zone}
    r = apps[0] if apps else {"by_zone": [], "by_city": []}
    for zone in r.get("by_zone", []):
        zone["surveyor_count"] = surveyor_map.get(zone["zone_id"], 0)
    return {
        "by_zone": r.get("by_zone", []),
        "by_city": r.get("by_city", []),
        "surveyor_coverage": staff_by_zone,
    }


# ── GET /analytics/processing-time ────────────────────────────────────────────
# Uses $bucketAuto for dynamic processing-time distribution

@router.get("/analytics/processing-time")
def analytics_processing_time():
    db = get_db()
    match_stage: dict = {"$match": {
        "timestamps.submitted_at": {"$exists": True},
        "timestamps.approved_at": {"$exists": True},
    }}
    days_project: dict = {"$project": {"days": {"$divide": [
        {"$subtract": ["$timestamps.approved_at", "$timestamps.submitted_at"]},
        86_400_000,
    ]}}}
    summary = list(db["land_applications"].aggregate([
        match_stage, days_project,
        {"$group": {
            "_id": None,
            "avg_days": {"$avg": "$days"},
            "min_days": {"$min": "$days"},
            "max_days": {"$max": "$days"},
            "count": {"$sum": 1},
        }},
        {"$project": {
            "_id": 0,
            "avg_days": {"$round": ["$avg_days", 1]},
            "min_days": {"$round": ["$min_days", 1]},
            "max_days": {"$round": ["$max_days", 1]},
            "count": 1,
        }},
    ]))
    buckets = list(db["land_applications"].aggregate([
        match_stage, days_project,
        {"$bucketAuto": {"groupBy": "$days", "buckets": 5, "output": {"count": {"$sum": 1}}}},
    ]))
    base = summary[0] if summary else {"avg_days": None, "min_days": None, "max_days": None, "count": 0}
    def _fmt(v: float | None) -> float:
        return round(v, 1) if v is not None else 0.0

    base["distribution"] = [
        {"range": f"{_fmt(b['_id']['min'])}–{_fmt(b['_id']['max'])} days", "count": b["count"]}
        for b in buckets
    ]
    return base


# ── GET /analytics/surveyors ───────────────────────────────────────────────────
# Uses $lookup to join survey_tasks + $unwind for per-task milestone processing

@router.get("/analytics/surveyors")
def analytics_surveyors():
    db = get_db()
    pipeline = [
        {"$match": {"role": "surveyor"}},
        {"$lookup": {
            "from": "survey_tasks",
            "localField": "staff_id",
            "foreignField": "assigned_to",
            "as": "tasks",
        }},
        {"$unwind": {"path": "$tasks", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$staff_id",
            "full_name": {"$first": "$full_name"},
            "is_active": {"$first": "$is_active"},
            "coverage_zones": {"$first": "$coverage_zones"},
            "max_tasks": {"$first": "$schedule.max_concurrent_tasks"},
            "total_tasks": {"$sum": {"$cond": [{"$ifNull": ["$tasks._id", False]}, 1, 0]}},
            "active_tasks": {"$sum": {"$cond": [{"$and": [
                {"$ifNull": ["$tasks._id", False]},
                {"$ne": ["$tasks.milestone", SurveyMilestone.registrar_reviewed.value]},
            ]}, 1, 0]}},
            "completed_tasks": {"$sum": {"$cond": [
                {"$eq": ["$tasks.milestone", SurveyMilestone.registrar_reviewed.value]}, 1, 0,
            ]}},
        }},
        {"$project": {
            "_id": 0,
            "staff_id": "$_id",
            "full_name": 1,
            "is_active": 1,
            "coverage_zones": 1,
            "max_tasks": {"$ifNull": ["$max_tasks", 3]},
            "total_tasks": 1,
            "active_tasks": 1,
            "completed_tasks": 1,
        }},
        {"$sort": {"active_tasks": -1}},
    ]
    return {"data": list(db["staff_members"].aggregate(pipeline))}


# ── GET /analytics/registrars ─────────────────────────────────────────────────
# Uses $lookup + $unwind on performance_logs to count transitions per registrar.
# (Applications don't store registrar_review.reviewed_by directly; we read the
#  audit log which records every transition with actor_type + actor_id.)

@router.get("/analytics/registrars")
def analytics_registrars():
    db = get_db()

    # Single aggregation: unwind events in performance_logs and count per registrar
    log_pipeline = [
        {"$unwind": "$events"},
        {"$match": {
            "events.actor_type": "registrar",
            "events.event_type": {"$in": [S.approved.value, S.rejected.value]},
        }},
        {"$group": {
            "_id": "$events.actor_id",
            "approved_count": {"$sum": {"$cond": [{"$eq": ["$events.event_type", S.approved.value]}, 1, 0]}},
            "rejected_count": {"$sum": {"$cond": [{"$eq": ["$events.event_type", S.rejected.value]}, 1, 0]}},
        }},
    ]
    log_stats = {r["_id"]: r for r in db["performance_logs"].aggregate(log_pipeline)}

    registrars = list(db["staff_members"].find({"role": "registrar"}, {"_id": 0}))
    result = []
    for r in registrars:
        sid = r["staff_id"]
        stats = log_stats.get(sid, {})
        approved = stats.get("approved_count", 0)
        rejected = stats.get("rejected_count", 0)
        total_reviewed = approved + rejected
        result.append({
            "staff_id": sid,
            "full_name": r.get("full_name", ""),
            "is_active": r.get("is_active", True),
            "total_reviewed": total_reviewed,
            "approved_count": approved,
            "rejected_count": rejected,
            "approval_rate": round(approved / total_reviewed * 100, 1) if total_reviewed > 0 else None,
        })
    result.sort(key=lambda x: x["total_reviewed"], reverse=True)
    return {"data": result}


# ── GET /analytics/geofeeds/parcels-near ──────────────────────────────────────
# Uses $geoNear for proximity search (requires 2dsphere index on parcels.geometry)

@router.get("/analytics/geofeeds/parcels-near")
def geofeed_parcels_near(lat: float = 31.9, lng: float = 35.2, radius_km: float = 100.0):
    db = get_db()
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lng, lat]},
                "distanceField": "dist_meters",
                "maxDistance": radius_km * 1000,
                "spherical": True,
            }
        },
        {"$limit": 100},
        {"$project": {
            "_id": 0,
            "parcel_number": 1,
            "zone_id": 1,
            "area_sqm": 1,
            "status": 1,
            "geometry": 1,
            "dist_meters": 1,
        }},
    ]
    try:
        parcels = list(db["parcels"].aggregate(pipeline))
    except Exception:
        parcels = []
    features = []
    for p in parcels:
        geom = p.pop("geometry", None)
        if geom:
            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "parcel_number": p.get("parcel_number", ""),
                    "zone_id": p.get("zone_id", ""),
                    "area_sqm": p.get("area_sqm"),
                    "status": p.get("status", ""),
                    "dist_meters": round(p.get("dist_meters", 0)),
                },
            })
    return {"type": "FeatureCollection", "features": features, "center": {"lat": lat, "lng": lng}}


# ── GET /analytics/certificates-by-month ──────────────────────────────────────

@router.get("/analytics/certificates-by-month")
def analytics_certificates_by_month(limit: int = 12):
    db = get_db()
    pipeline = [
        {"$match": {"issued_at": {"$exists": True}}},
        {"$project": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$issued_at"}}}},
        {"$group": {"_id": "$month", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "month": "$_id", "count": 1}},
    ]
    return {"data": list(db["certificates"].aggregate(pipeline))}


# ── GET /analytics/export/csv ──────────────────────────────────────────────────
# Export: applications summary as CSV for management reports

@router.get("/analytics/export/csv")
def export_applications_csv():
    db = get_db()
    apps = list(db["land_applications"].find(
        {},
        {
            "_id": 0,
            "application_id": 1,
            "application_type": 1,
            "status": 1,
            "priority": 1,
            "parcel_ref.zone_id": 1,
            "parcel_ref.parcel_number": 1,
            "applicant_ref.applicant_id": 1,
            "timestamps.submitted_at": 1,
            "timestamps.approved_at": 1,
            "timestamps.updated_at": 1,
        }
    ).limit(5000))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Application ID", "Type", "Status", "Priority",
        "Zone", "Parcel Number", "Applicant ID",
        "Submitted At", "Approved At", "Last Updated",
    ])
    for a in apps:
        ts = a.get("timestamps") or {}
        pr = a.get("parcel_ref") or {}
        ar = a.get("applicant_ref") or {}

        def _fmt(v):
            if v is None:
                return ""
            if isinstance(v, datetime):
                return v.strftime("%Y-%m-%d %H:%M")
            return str(v)

        writer.writerow([
            a.get("application_id", ""),
            a.get("application_type", ""),
            a.get("status", ""),
            a.get("priority", ""),
            pr.get("zone_id", ""),
            pr.get("parcel_number", ""),
            ar.get("applicant_id", ""),
            _fmt(ts.get("submitted_at")),
            _fmt(ts.get("approved_at")),
            _fmt(ts.get("updated_at")),
        ])

    output.seek(0)
    filename = f"lrmis_applications_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )