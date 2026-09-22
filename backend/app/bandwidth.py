"""Bandwidth / data-reduction endpoint for the pitch.

Compares raw-video upload (counterfactual) against actual edge metadata
upload. All assumptions are documented in the response so judges can
audit the math.
"""
import json
from fastapi import APIRouter
from app.events import get_all_events

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

ASSUMED_CAMERAS_PER_BUS = 4
ASSUMED_BITRATE_MBPS = 8
ASSUMED_HOURS_PER_DAY_PER_BUS = 14


@router.get("/bandwidth")
def bandwidth():
    try:
        events = get_all_events()
    except Exception as exc:
        return {"error": f"event store unavailable: {exc}"}

    edge_bytes = sum(len(json.dumps(e, default=str)) for e in events)

    raw_bytes_per_bus_per_day = (
        ASSUMED_CAMERAS_PER_BUS
        * ASSUMED_BITRATE_MBPS
        * 1_000_000 / 8
        * ASSUMED_HOURS_PER_DAY_PER_BUS
        * 3600
    )
    return {
        "events_observed": len(events),
        "edge_metadata_bytes_total": edge_bytes,
        "edge_metadata_bytes_per_event": round(edge_bytes / max(len(events), 1), 1),
        "counterfactual": {
            "cameras_per_bus": ASSUMED_CAMERAS_PER_BUS,
            "bitrate_mbps_per_camera": ASSUMED_BITRATE_MBPS,
            "hours_per_day_per_bus": ASSUMED_HOURS_PER_DAY_PER_BUS,
            "raw_video_bytes_per_bus_per_day": int(raw_bytes_per_bus_per_day),
            "raw_video_gb_per_bus_per_day": round(raw_bytes_per_bus_per_day / 1e9, 2),
        },
        "reduction_ratio": round(
            raw_bytes_per_bus_per_day / max(edge_bytes or 1, 1), 1
        ),
        "method_note": (
            "Raw-video counterfactual assumes continuous 1080p@25fps H.264 at 8 Mbps "
            "from 4 cameras for 14 hours per bus per day. Actual edge uploads only "
            "structured event JSON plus a small JPEG evidence crop per event. "
            "Illustrative for prototype demonstration."
        ),
    }
