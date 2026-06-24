"""
Seed sample parcels with GeoJSON geometry so the map has data to display.
Run from lrmis-backend/:  python -m scripts.seed_parcels

Parcels are placed around Ramallah, Palestine (31.9°N, 35.2°E).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from app.database import get_db


PARCELS = [
    {
        "parcel_code": "RM-Z01-B12-P145",
        "parcel_number": "PARCEL-001",
        "block_number": "12",
        "basin_number": "3",
        "zone_id": "ZONE-A",
        "area_sqm": 850.5,
        "land_use": "residential",
        "registration_status": "registered",
        "address_hint": "Ramallah - Al Tireh",
        "dispute_state": "none",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.1990, 31.9010],
                [35.2010, 31.9010],
                [35.2010, 31.9025],
                [35.1990, 31.9025],
                [35.1990, 31.9010],
            ]],
        },
    },
    {
        "parcel_code": "RM-Z01-B12-P200",
        "parcel_number": "PARCEL-002",
        "block_number": "12",
        "basin_number": "3",
        "zone_id": "ZONE-A",
        "area_sqm": 620.0,
        "land_use": "commercial",
        "registration_status": "registered",
        "address_hint": "Ramallah - City Center",
        "dispute_state": "none",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.2020, 31.9015],
                [35.2040, 31.9015],
                [35.2040, 31.9030],
                [35.2020, 31.9030],
                [35.2020, 31.9015],
            ]],
        },
    },
    {
        "parcel_code": "RM-Z02-B05-P033",
        "parcel_number": "PARCEL-003",
        "block_number": "5",
        "basin_number": "1",
        "zone_id": "ZONE-B",
        "area_sqm": 1200.0,
        "land_use": "agricultural",
        "registration_status": "pending",
        "address_hint": "Bireh - Beit Ila",
        "dispute_state": "none",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.2100, 31.9050],
                [35.2130, 31.9050],
                [35.2130, 31.9070],
                [35.2100, 31.9070],
                [35.2100, 31.9050],
            ]],
        },
    },
    {
        "parcel_code": "RM-Z02-B05-P044",
        "parcel_number": "PARCEL-004",
        "block_number": "5",
        "basin_number": "1",
        "zone_id": "ZONE-B",
        "area_sqm": 750.0,
        "land_use": "residential",
        "registration_status": "registered",
        "address_hint": "Bireh - Ein Munjed",
        "dispute_state": "disputed",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.2140, 31.9055],
                [35.2160, 31.9055],
                [35.2160, 31.9072],
                [35.2140, 31.9072],
                [35.2140, 31.9055],
            ]],
        },
    },
    {
        "parcel_code": "RM-ZC-B08-P099",
        "parcel_number": "PARCEL-005",
        "block_number": "8",
        "basin_number": "2",
        "zone_id": "ZONE-C",
        "area_sqm": 500.0,
        "land_use": "residential",
        "registration_status": "registered",
        "address_hint": "Ramallah - Masyoun",
        "dispute_state": "none",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.1950, 31.8990],
                [35.1970, 31.8990],
                [35.1970, 31.9005],
                [35.1950, 31.9005],
                [35.1950, 31.8990],
            ]],
        },
    },
    {
        "parcel_code": "RM-ZA-B03-P011",
        "parcel_number": "PARCEL-006",
        "block_number": "3",
        "basin_number": "1",
        "zone_id": "ZONE-A",
        "area_sqm": 980.0,
        "land_use": "mixed",
        "registration_status": "pending",
        "address_hint": "Ramallah - Jifna Road",
        "dispute_state": "none",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [35.1960, 31.9040],
                [35.1985, 31.9040],
                [35.1985, 31.9058],
                [35.1960, 31.9058],
                [35.1960, 31.9040],
            ]],
        },
    },
]


def seed():
    db = get_db()
    col = db["parcels"]
    now = datetime.now(timezone.utc)
    inserted = 0
    skipped = 0
    for p in PARCELS:
        p["created_at"] = now
        p["updated_at"] = now
        try:
            col.update_one(
                {"parcel_code": p["parcel_code"]},
                {"$setOnInsert": p},
                upsert=True,
            )
            inserted += 1
        except Exception as e:
            print(f"  SKIP {p['parcel_code']}: {e}")
            skipped += 1
    print(f"Seeded {inserted} parcels ({skipped} skipped). Total in DB: {col.count_documents({})}")


if __name__ == "__main__":
    seed()
