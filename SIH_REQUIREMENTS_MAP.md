# SIH 26124 — Requirements Coverage Map
## UrbanPulse: AI-Powered Mobile Urban Intelligence Platform

**Team:** Signal Sync  
**Repo:** https://github.com/Signal-Sync/UrbanPulse-  
**Prototype Status:** ~80% feature coverage  
**TRL:** 4 (lab-validated on real video, CPU-only edge)

---

## A. Onboard Edge AI Processing

| # | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| A1a | Pothole detection | ✅ Working | `best.pt` (YOLOv8n), class `pothole` | 62 pothole events in DB |
| A1b | Damaged road / cracks | ✅ Working | `best.pt`, class `crack` | 87 crack events in DB |
| A1c | Road patches | ✅ Working | `best.pt`, class `patch` | 51 patch events in DB |
| A1d | Waterlogging | ❌ Roadmap | Rule-based HSV heuristic designed, not deployed | — |
| A1e | Missing zebra crossing | ❌ Roadmap | Absence-of-stripe heuristic designed | — |
| A1f | Missing road divider | ❌ Roadmap | Requires lane-segmentation model | — |
| A1g | Damaged traffic signboard | ❌ Roadmap | Requires dedicated classifier | — |
| A2 | Vehicle detection + classification + counting | ✅ Working | YOLOv8n COCO, classes: car/bus/truck/bike/motorcycle | Traffic camera shows live count |
| A3 | Traffic bottleneck detection | ✅ Working | Vehicle-count threshold heuristic in `runtime.py` | MEDIUM/HIGH congestion events |
| A4 | Vulnerable pedestrian (school zone) | ⚠️ Backend only | `SCHOOL_ZONE_PEDESTRIAN` event in `runtime.py:300`, schools.json (76 KB, 200+ schools) | Not surfaced in demo route yet |
| A5 | Hit-and-run + ANPR + plate extraction | ⚠️ Endpoint only | `/api/incidents/anpr` implemented; plate OCR pipeline designed | Returns `{incidents: [], count: 0}` honestly |
| A6 | Edge processing (bandwidth minimization) | ✅ Working | 320 px downscale, frame-skip, JSON-only sync | See C3 |
| A7 | Multi-camera fusion | ✅ Partial | 2 cameras (road + traffic) running concurrently | `/api/status` shows both |

---

## B. Centralized Intelligence Platform

| # | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| B1 | Fleet-wide event aggregation | ✅ Working | FastAPI + SQLite (`events.sqlite3`), 1,000+ events | `GET /api/events` |
| B2 | GIS map visualization | ✅ Working | React + Leaflet, 5 tile providers | Screenshot in pitch |
| B3 | Congestion heat map | ✅ Working | Heat-map mode in `GISMap.jsx` | Screenshot in pitch |
| B4 | Infrastructure deficiency map | ✅ Working | Density circles by defect type | Heatmap panel |
| B5 | Origin-Destination matrix | ❌ Roadmap | Requires trip inference from GPS traces | — |
| B6 | Route delay estimation | ❌ Roadmap | Requires schedule table | — |
| B7 | Actionable insights / reports | ⚠️ Partial | Incident workflow (DETECTED → VERIFIED → ASSIGNED → RESOLVED → CLOSED) | Incident Center page |
| B8 | Secure alert sharing | ⚠️ Partial | REST endpoints exposed, no auth token yet | — |

---

## C. Cross-Cutting Requirements

| # | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| C1 | Edge optimization | ✅ Working | 320 px downscale, frame-skip=4, CPU inference | ~100 ms/frame |
| C2 | Confidence scoring + FP reduction | ✅ Working | Per-class confidence, spatial dedup (15 m), temporal cooldown (60 s) | 800-1800/min → 4-20/min |
| C3 | Bandwidth minimization proof | ✅ Working | `/api/metrics/bandwidth` endpoint | **163,738× reduction** (201.6 GB/bus/day raw → 1.2 MB/day edge) |
| C4 | Evidence / audit trail | ✅ Working | JPEG evidence crop per event + status_history JSON array | `/evidence/{event_id}.jpg` |
| C5 | Public safety | ⚠️ Backend only | School-zone event emits; UI surfacing pending | — |

---

## D. Verified Metrics

| Metric | Value |
|---|---|
| Events captured in current session | 1,011 |
| Edge inference latency | ~100 ms/frame |
| Edge FPS | 6–8 (CPU-only, Intel i3-10110U) |
| Avg event size | 1.2 KB |
| Raw video counterfactual | 201.6 GB/bus/day |
| Edge upload actual | ~1.2 MB/bus/day |
| **Bandwidth reduction** | **163,738×** |
| Notification rate (before → after) | 800–1800/min → 4–20/min |
| Spatial dedup radius | 15 m (road), 30 m (congestion), 100 m (school) |
| Temporal cooldown | 60 s (road), 120 s (congestion) |

---

## E. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Edge inference | Ultralytics YOLOv8n | Road defects + vehicle detection |
| Edge processing | OpenCV | Frame decode, downscale, annotation |
| Tracking | ByteTrack (via Ultralytics) | Persistent vehicle IDs |
| Backend | FastAPI + Uvicorn | Async REST API + MJPEG streaming |
| Data | SQLite + WAL | Event store (portable to PostgreSQL + PostGIS in production) |
| Frontend | React 18 + Vite + Tailwind | Dashboard |
| GIS | Leaflet | 5 tile providers (Google, Carto) |
| Charts | Custom heat-map circles | Density visualization by severity |

---

## F. Honest Gaps & Roadmap

| Gap | Why | Timeline |
|---|---|---|
| Waterlogging / zebra / divider / signboard detection | Model trained on 4 classes; missing 4 defect classes | 2 weeks (retrain on RDD2022 + Chennai data) |
| Real ANPR plate OCR | Endpoint ready; edge doesn't emit plate events | 1 week (integrate PaddleOCR) |
| O-D matrix, route delay | Requires historical schedule data | 3 weeks |
| PostgreSQL + PostGIS | Prototype uses SQLite | 1 week migration |
| INT8 quantization / TensorRT | CPU prototype | 3 days on Jetson Orin |
| Secure alert auth | No token auth on endpoints | 2 days |
| Multi-camera (4 vs 2) | Road + traffic deployed | 1 week |
| N-frame confirmation | Single-frame events | 1 day |

---

## G. Demo Evidence

- **Live**: 2 cameras running, real-time YOLO inference, ~1,000 events in DB
- **Bandwidth proof**: `/api/metrics/bandwidth` returns 163,738× reduction
- **Video**: `demo_v1.mp4` (recorded live session)
- **Repo**: https://github.com/Signal-Sync/UrbanPulse-
- **GitHub README**: See `START_HERE.md` and this file

---
 
**Team Signal Sync**
