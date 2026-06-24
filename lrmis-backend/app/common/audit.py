from datetime import datetime, timezone

from app.database import get_db


def log_event(
    application_id: str,
    event_type: str,
    actor_type: str,
    actor_id: str,
    meta: dict | None = None,
) -> None:
    db = get_db()
    db["performance_logs"].update_one(
        {"application_id": application_id},
        {
            "$push": {
                "events": {
                    "event_type": event_type,
                    "actor_type": actor_type,
                    "actor_id": actor_id,
                    "meta": meta or {},
                    "timestamp": datetime.now(timezone.utc),
                }
            }
        },
        upsert=True,
    )
