from app.database import get_db


def pick_surveyor(zone_id: str, required_skill: str) -> dict | None:
    """
    Finds the least-loaded available surveyor for the given zone and skill.
    Returns the staff_members document, or None if no candidate is found.
    """
    db = get_db()

    # TODO: extend the query to include rating, distance-to-parcel, and schedule data
    candidates = list(
        db["staff_members"].find(
            {
                "role": "surveyor",
                "zones": zone_id,
                "skills": required_skill,
                "availability": True,
            }
        )
    )

    if not candidates:
        return None

    # Rank by active (non-completed) task count — fewest tasks first
    # TODO: replace with weighted scoring (task load × 0.5, zone expertise × 0.3, rating × 0.2)
    task_counts = {
        c["staff_code"]: db["survey_tasks"].count_documents(
            {"assigned_surveyor": c["staff_code"], "status": {"$ne": "completed"}}
        )
        for c in candidates
    }
    candidates.sort(key=lambda c: task_counts.get(c["staff_code"], 0))
    return candidates[0]
