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
    db.land_applications.create_index("idempotency_key", unique=True, sparse=True)
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
    db["applicants"].create_index("applicant_id", unique=True)
    db["applicants"].create_index("identity.national_id", unique=True)

    # application_documents
    db["application_documents"].create_index("application_id")
    db["application_documents"].create_index("document_id", unique=True)

    # objections
    db["objections"].create_index("application_id")
    db["objections"].create_index("objection_id", unique=True)

    # staff_members — staff_id is our generated key; staff_code is the spec-required field
    db["staff_members"].create_index("staff_id", unique=True)
    db["staff_members"].create_index("staff_code", unique=True, sparse=True)
    db["staff_members"].create_index("role")

    # survey_tasks
    db["survey_tasks"].create_index("application_id")
    db["survey_tasks"].create_index("assigned_to")

    # certificates
    db["certificates"].create_index("certificate_id", unique=True)

    print("All indexes created successfully.")


if __name__ == "__main__":
    create_indexes()
