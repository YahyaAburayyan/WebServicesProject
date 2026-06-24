"""
Seed staff members (registrars + surveyors).
Run from lrmis-backend/:  python -m scripts.seed_staff
Safe to re-run — uses upsert on staff_id.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from app.database import get_db

NOW = datetime.now(timezone.utc)

DEFAULT_SCHEDULE = {
    "working_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "shift_start": "08:00",
    "shift_end": "16:00",
    "max_concurrent_tasks": 5,
}

STAFF = [
    # ── Registrars ────────────────────────────────────────────────
    {
        "staff_id":   "STAF-2026-0001",
        "staff_code": "REG-001",
        "full_name":  "Omar Al-Khalidi",
        "role":       "registrar",
        "national_id": "REG-NID-001",
        "contacts":   {"email": "omar.khalidi@lrmis.ps", "phone": "+970-599-100001"},
        "coverage_zones": [],
        "skills":     ["legal_review", "certificate_issuance"],
        "schedule":   DEFAULT_SCHEDULE,
        "workload":   {"current_tasks": 0, "max_tasks": 5},
        "performance": {"total_tasks_completed": 0, "avg_completion_days": None, "on_time_rate": None},
        "is_active":  True,
    },
    {
        "staff_id":   "STAF-2026-0002",
        "staff_code": "REG-002",
        "full_name":  "Layla Mansour",
        "role":       "registrar",
        "national_id": "REG-NID-002",
        "contacts":   {"email": "layla.mansour@lrmis.ps", "phone": "+970-599-100002"},
        "coverage_zones": [],
        "skills":     ["legal_review", "pre_check", "document_review"],
        "schedule":   DEFAULT_SCHEDULE,
        "workload":   {"current_tasks": 0, "max_tasks": 5},
        "performance": {"total_tasks_completed": 0, "avg_completion_days": None, "on_time_rate": None},
        "is_active":  True,
    },

    # ── Surveyors ─────────────────────────────────────────────────
    {
        "staff_id":   "STAF-2026-0003",
        "staff_code": "SRV-001",
        "full_name":  "Kareem Nasser",
        "role":       "surveyor",
        "national_id": "SRV-NID-001",
        "contacts":   {"email": "kareem.nasser@lrmis.ps", "phone": "+970-599-200001"},
        "coverage_zones": ["ZONE-A", "ZONE-B"],
        "skills":     ["boundary_survey", "gps_mapping", "first_registration"],
        "schedule":   DEFAULT_SCHEDULE,
        "workload":   {"current_tasks": 0, "max_tasks": 3},
        "performance": {"total_tasks_completed": 0, "avg_completion_days": None, "on_time_rate": None},
        "is_active":  True,
    },
    {
        "staff_id":   "STAF-2026-0004",
        "staff_code": "SRV-002",
        "full_name":  "Hana Barakat",
        "role":       "surveyor",
        "national_id": "SRV-NID-002",
        "contacts":   {"email": "hana.barakat@lrmis.ps", "phone": "+970-599-200002"},
        "coverage_zones": ["ZONE-B", "ZONE-C"],
        "skills":     ["boundary_survey", "subdivision", "aerial_mapping"],
        "schedule":   DEFAULT_SCHEDULE,
        "workload":   {"current_tasks": 0, "max_tasks": 3},
        "performance": {"total_tasks_completed": 0, "avg_completion_days": None, "on_time_rate": None},
        "is_active":  True,
    },
    {
        "staff_id":   "STAF-2026-0005",
        "staff_code": "SRV-003",
        "full_name":  "Tariq Saleh",
        "role":       "surveyor",
        "national_id": "SRV-NID-003",
        "contacts":   {"email": "tariq.saleh@lrmis.ps", "phone": "+970-599-200003"},
        "coverage_zones": ["ZONE-A", "ZONE-C"],
        "skills":     ["boundary_survey", "gps_mapping", "dispute_resolution"],
        "schedule":   DEFAULT_SCHEDULE,
        "workload":   {"current_tasks": 0, "max_tasks": 3},
        "performance": {"total_tasks_completed": 0, "avg_completion_days": None, "on_time_rate": None},
        "is_active":  True,
    },
]


def seed():
    db = get_db()
    col = db["staff_members"]
    inserted = skipped = 0

    for s in STAFF:
        s["created_at"] = NOW
        s["updated_at"] = NOW
        result = col.update_one(
            {"staff_id": s["staff_id"]},
            {"$setOnInsert": s},
            upsert=True,
        )
        if result.upserted_id:
            print(f"  + Inserted  {s['staff_id']}  ({s['role']})  — {s['full_name']}")
            inserted += 1
        else:
            print(f"  ~ Skipped   {s['staff_id']}  (already exists)")
            skipped += 1

    # Keep the counter ahead of seeded IDs so auto-generated IDs don't collide
    db["counters"].update_one(
        {"_id": "staff_id"},
        {"$max": {"seq": len(STAFF)}},
        upsert=True,
    )

    print(f"\nDone — {inserted} inserted, {skipped} skipped.")
    print(f"Total staff in DB: {col.count_documents({})}")
    print("\nRegistrar login IDs:  STAF-2026-0001, STAF-2026-0002")
    print("Surveyor login IDs:   STAF-2026-0003, STAF-2026-0004, STAF-2026-0005")


if __name__ == "__main__":
    seed()
