"""ANPR incident endpoint.

Surfaces events whose metadata carries plate information, plus events
explicitly marked HIT_AND_RUN / ANPR_DETECTION / RASH_DRIVING.

IMPORTANT: This endpoint does NOT fabricate plate data. If the edge
pipeline has not emitted a plate-bearing event, /api/incidents/anpr
returns an empty list. That is correct behaviour.
"""
import logging
from fastapi import APIRouter, Query, HTTPException

from app.events import get_all_events

LOG = logging.getLogger("urbanpulse.anpr")
router = APIRouter(prefix="/api/incidents", tags=["anpr"])

_ANPR_EVENT_TYPES = {"HIT_AND_RUN", "ANPR_DETECTION", "RASH_DRIVING", "DANGEROUS_OVERTAKING"}


def _extract_anpr(e: dict):
    m = e.get("metadata") or {}
    plate = m.get("plate") or m.get("plate_text") or m.get("registration")
    event_type = e.get("event_type", "")
    is_anpr = bool(plate) or event_type in _ANPR_EVENT_TYPES
    if not is_anpr:
        return None
    return {
        "incident_id": e.get("event_id"),
        "event_type": event_type or "ANPR_DETECTION",
        "plate": plate,
        "plate_confidence": m.get("plate_confidence") or m.get("plate_conf"),
        "plate_raw_text": m.get("plate_raw_text") or m.get("plate_raw"),
        "vehicle_type": e.get("vehicle_type") or m.get("vehicle_type"),
        "track_id": e.get("track_id"),
        "bus_id": e.get("bus_id"),
        "camera_id": e.get("camera_id"),
        "timestamp": e.get("timestamp"),
        "latitude": e.get("latitude"),
        "longitude": e.get("longitude"),
        "gps_source": e.get("gps_source"),
        "evidence_path": e.get("evidence_path"),
        "confidence": e.get("confidence"),
        "severity": e.get("severity"),
        "status": e.get("status"),
        "status_history": e.get("status_history") or [],
        "method": m.get("method", "edge-anpr-pipeline"),
    }


@router.get("/anpr")
def list_anpr_incidents(
    limit: int = Query(200, ge=1, le=1000),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    try:
        events = get_all_events()
    except Exception as exc:
        LOG.exception("Failed to read events store")
        raise HTTPException(500, f"Event store unavailable: {exc}") from exc

    out = []
    for e in events:
        rec = _extract_anpr(e)
        if rec is None:
            continue
        if min_confidence > 0 and (rec.get("plate_confidence") or 0) < min_confidence:
            continue
        out.append(rec)

    out.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    out = out[:limit]
    return {
        "incidents": out,
        "count": len(out),
        "note": (
            "Populated from events whose metadata contains plate information. "
            "If empty, the edge pipeline has not yet emitted an ANPR-bearing "
            "event for this session. No plate data is fabricated."
        ),
    }


@router.get("/anpr/{incident_id}")
def get_anpr_incident(incident_id: str):
    try:
        events = get_all_events()
    except Exception as exc:
        raise HTTPException(500, f"Event store unavailable: {exc}") from exc

    for e in events:
        if e.get("event_id") == incident_id:
            rec = _extract_anpr(e)
            if rec is None:
                raise HTTPException(404, "Event exists but carries no ANPR metadata")
            return rec
    raise HTTPException(404, f"Incident {incident_id} not found")
