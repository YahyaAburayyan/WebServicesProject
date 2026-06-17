from fastapi import APIRouter

from app.common.schemas import Message

router = APIRouter(prefix="/analytics", tags=["Analytics & Map (Group)"])

_EMPTY_GEOJSON = {"type": "FeatureCollection", "features": []}


@router.get("/kpis", response_model=Message)
def get_kpis():
    # TODO: aggregate total applications, avg processing days, certificate rate, rejection rate
    return Message(message="TODO: return KPI metrics")


@router.get("/applications-by-status", response_model=Message)
def applications_by_status():
    # TODO: $group land_applications by status; return list of {status, count}
    return Message(message="TODO: return applications grouped by status")


@router.get("/applications-by-zone", response_model=Message)
def applications_by_zone():
    # TODO: $group land_applications by parcel_ref.zone_id; return list of {zone_id, count}
    return Message(message="TODO: return applications grouped by zone")


@router.get("/processing-time", response_model=Message)
def processing_time():
    # TODO: compute avg/p50/p95 from (timestamps.closed_at - timestamps.submitted_at)
    return Message(message="TODO: return processing time statistics")


@router.get("/surveyors", response_model=Message)
def surveyor_stats():
    # TODO: per-surveyor task count, avg completion days, on-time rate
    return Message(message="TODO: return surveyor analytics")


@router.get("/registrars", response_model=Message)
def registrar_stats():
    # TODO: per-registrar review count, approval/rejection rates, avg review time
    return Message(message="TODO: return registrar analytics")


@router.get("/geofeeds/parcels")
def geofeed_parcels():
    # TODO: project parcels collection into GeoJSON Feature objects
    return _EMPTY_GEOJSON


@router.get("/geofeeds/pending-heatmap")
def geofeed_pending_heatmap():
    # TODO: aggregate pending applications by parcel centroid for heatmap rendering
    return _EMPTY_GEOJSON
