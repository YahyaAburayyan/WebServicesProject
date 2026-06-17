"""
Run with:  python -m scripts.seed_data
Inserts one sample parcel with a GeoJSON Polygon (upsert — safe to re-run).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db

SAMPLE_PARCEL = {
    "parcel_code": "PARCEL-001",
    "zone_id": "ZONE-A",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [36.8172, 1.2921],
                [36.8182, 1.2921],
                [36.8182, 1.2931],
                [36.8172, 1.2931],
                [36.8172, 1.2921],
            ]
        ],
    },
    "area_sqm": 1000.0,
    "description": "Sample parcel for development and testing",
}


def seed() -> None:
    db = get_db()
    result = db["parcels"].update_one(
        {"parcel_code": SAMPLE_PARCEL["parcel_code"]},
        {"$set": SAMPLE_PARCEL},
        upsert=True,
    )
    if result.upserted_id:
        print(f"Inserted sample parcel: {result.upserted_id}")
    else:
        print("Sample parcel already exists — updated in place.")


if __name__ == "__main__":
    seed()
