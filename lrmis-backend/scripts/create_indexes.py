"""
Run with:  python -m scripts.create_indexes
Must be executed from the lrmis-backend/ directory.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import ASCENDING, GEOSPHERE

from app.database import get_db


def create_indexes() -> None:
    db = get_db()

    # land_applications
    db["land_applications"].create_index("application_id", unique=True)
    db["land_applications"].create_index("status")
    db["land_applications"].create_index("application_type")
    db["land_applications"].create_index("parcel_ref.parcel_number")
    db["land_applications"].create_index("parcel_ref.zone_id")
    db["land_applications"].create_index("timestamps.submitted_at")

    # parcels
    db["parcels"].create_index("parcel_code", unique=True)
    db["parcels"].create_index([("geometry", GEOSPHERE)])
    db["parcels"].create_index("zone_id")

    # applicants
    db["applicants"].create_index("identity.national_id", unique=True)

    # staff_members
    db["staff_members"].create_index("staff_code", unique=True)

    # survey_tasks
    db["survey_tasks"].create_index("application_id")

    # certificates
    db["certificates"].create_index("certificate_id", unique=True)

    print("All indexes created successfully.")


if __name__ == "__main__":
    create_indexes()
