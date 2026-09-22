"""Two independent bounded camera workers on one bus edge device."""
import base64
from collections import Counter, deque
from datetime import datetime, timezone
import json
import logging
import math
import os
from pathlib import Path
import threading
import time
from uuid import uuid4

from edge.outbox import Outbox
from edge.intelligence import GPSProvider, TrafficRules, nearest_school

BASE = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("urbanpulse.edge")


def load_config():
    path = Path(os.getenv("EDGE_CONFIG", str(BASE / "edge" / "config.json")))
    config = json.loads(path.read_text())
    for key in ("road_model", "road_video", "traffic_model", "traffic_video"):
        value = Path(os.getenv(key.upper(), config[key])).expanduser()
        config[key] = str(value if value.is_absolute() else BASE / value)
    config["device"] = os.getenv("AI_DEVICE", config["device"])
    if Path(config["road_video"]).resolve() == Path(config["traffic_video"]).resolve():
        raise ValueError("Road and traffic cameras require independent video sources")
    for key in ("target_fps", "imgsz", "display_width", "cpu_threads", "route_duration_seconds",
                "congestion_window_seconds", "congestion_hold_seconds",
                "congestion_cooldown_seconds", "road_cooldown_seconds"):
        if config[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if not 0 <= config["congestion_low_max"] < config["congestion_medium_max"]:
        raise ValueError("Congestion thresholds must be ordered")
    if not 0 < config["confidence"] <= 1:
        raise ValueError("confidence must be in (0,1]")
    if len(config["prototype_route"]) < 2:
        raise ValueError("Prototype route requires at least two coordinates")
    for lat, lon in config["prototype_route"]:
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("Invalid route coordinate")
    settings_path = BASE / "edge" / "enhancements.json"
    if settings_path.exists():
        config.update(json.loads(settings_path.read_text()))
    return config


def route_position(config, elapsed):
    # Shared bus clock: different camera durations do not put the bus in two places.
    progress = (elapsed % config["route_duration_seconds"]) / config["route_duration_seconds"]
    route = config["prototype_route"]
    offset = progress * (len(route) - 1)
    index = min(int(offset), len(route) - 2)
    fraction = offset - index
    a, b = route[index], route[index + 1]
    return tuple(a[i] + fraction * (b[i] - a[i]) for i in (0, 1))


class CameraWorker:
    def __init__(self, kind, config, outbox, started, gps):
        self.kind, self.config, self.outbox, self.started = kind, config, outbox, started
        self.gps = gps
        self.frame_fix = None
        self.schools = []
        if config.get("school_context", {}).get("enabled"):
            try:
                self.schools = json.loads((BASE / "edge" / "schools.json").read_text())
            except (OSError, ValueError):
                LOG.warning("School dataset unavailable; school context disabled")
        self.camera_id = "FRONT_CAMERA" if kind == "road" else "TRAFFIC_CAMERA"
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.jpeg = None
        self.sequence = 0
        self.published_at = None
        self.state = {"status": "starting", "error": None, "camera_id": self.camera_id,
                      "bus_id": config["bus_id"], "source": "PRERECORDED_VIDEO_AI",
                      "gps_source": "SIMULATED_ROUTE", "classes": {}, "inference_ms": None,
                      "processed_fps": None, "vehicle_count": None, "counts": {},
                      "congestion_level": "UNKNOWN", "signal_state": "UNKNOWN",
                      "violations_enabled": False}
        self.thread = threading.Thread(target=self.run, name=f"{kind}-camera", daemon=True)

    def snapshot(self):
        with self.lock:
            value = dict(self.state)
            value["frame_age_ms"] = (time.monotonic() - self.published_at) * 1000 if self.published_at else None
            return value

    def event(self, event_type, severity, source_seconds, source_frame, metadata, confidence=None,
              vehicle_count=None, evidence=None):
        fix = self.frame_fix or self.gps.read()
        if not fix.get("valid"):
            return None
        lat, lon = fix["latitude"], fix["longitude"]
        value = {"event_id": str(uuid4()), "event_type": event_type, "severity": severity,
                 "confidence": confidence, "timestamp": datetime.now(timezone.utc).isoformat(),
                 "bus_id": self.config["bus_id"], "camera_id": self.camera_id,
                 "latitude": lat, "longitude": lon, "gps_source": fix["source"],
                 "source": "PRERECORDED_VIDEO_AI", "vehicle_count": vehicle_count,
                 "metadata": {**metadata, "source_video_seconds": source_seconds,
                              "source_frame": source_frame, "model": self.model_name,
                              "inference_ms": self.inference_ms, "gps_accuracy_m": fix.get("accuracy_m"),
                              "gps_timestamp": fix.get("timestamp"), "location_basis": "camera/bus position, not surveyed object position"}}
        if evidence is not None and self.config["evidence"]:
            value["evidence_jpeg_base64"] = base64.b64encode(evidence).decode("ascii")
        return value

    def run(self):
        cap = None
        try:
            import cv2
            import torch
            from ultralytics import YOLO
            from edge.traffic_core import CONGESTION_THRESHOLDS, congestion_level, classify_light_color
            cfg = self.config
            model_path, video_path = Path(cfg[f"{self.kind}_model"]), Path(cfg[f"{self.kind}_video"])
            if not model_path.is_file():
                raise FileNotFoundError(f"Model missing: {model_path}. Supply the existing trained weights.")
            if not video_path.is_file():
                raise FileNotFoundError(f"Video missing: {video_path}. Supply this camera's independent recording.")
            device = cfg["device"]
            if device == "auto":
                device = "0" if torch.cuda.is_available() else "cpu"
            if device != "cpu" and not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but unavailable in this Python environment")
            self.model_name = model_path.name
            model = YOLO(str(model_path))
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise RuntimeError(f"Cannot decode video: {video_path}")
            fps, total = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if not math.isfinite(fps) or fps <= 0 or total <= 0:
                raise RuntimeError("Prerecorded source requires valid FPS and frame count")
            duration = total / fps
            names = model.names
            allowed_names = {"person", "bicycle", "car", "motorcycle", "bus", "truck", "traffic light"}
            class_ids = [i for i, name in names.items() if name in allowed_names]
            if self.kind == "traffic" and not any(names[i] == "car" for i in class_ids):
                raise RuntimeError("Traffic weights do not contain the required vehicle classes")
            profile = cfg.get(f"{self.kind}_inference", {})
            selected_imgsz = profile.get("gpu_imgsz" if device != "cpu" else "cpu_imgsz", cfg["imgsz"])
            selected_conf = profile.get("confidence", cfg["confidence"])
            tracker_name = cfg.get("traffic_tracker", "bytetrack.yaml")
            if tracker_name not in ("bytetrack.yaml", "botsort.yaml"):
                raise ValueError("Unsupported tracker configuration")
            rules = TrafficRules(cfg.get("violations", {}), video_path)
            kwargs = dict(imgsz=selected_imgsz, conf=selected_conf, device=device,
                          half=device != "cpu", verbose=False)
            if self.kind == "traffic":
                kwargs["classes"] = class_ids
            # Initialize inference/tracker once before starting playback timing.
            ok, warm_frame = cap.read()
            if not ok:
                raise RuntimeError("Cannot read first source frame")
            if self.kind == "traffic":
                model.track(warm_frame, persist=True, tracker=tracker_name, **kwargs)
                for tracker in model.predictor.trackers:
                    tracker.reset()
            else:
                model.predict(warm_frame, **kwargs)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            CONGESTION_THRESHOLDS.update(low=cfg["congestion_low_max"], medium=cfg["congestion_medium_max"])
            with self.lock:
                self.state.update(status="running", device=str(device), fp16=device != "cpu",
                    model=self.model_name, classes=names, source_fps=fps, imgsz=selected_imgsz,
                    violations_enabled=rules.enabled if self.kind=="traffic" else False,
                    violation_status=rules.reason, depth_measured=False,
                    source_width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    source_height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), source_duration_seconds=duration)
            playback_start = time.monotonic()
            samples, counts_window = deque(maxlen=240), deque(maxlen=240)
            level_since, previous_level = None, "UNKNOWN"
            last_absolute, last_loop = -1, 0
            while not self.stop.is_set():
                cycle = time.monotonic()
                absolute = int((cycle - playback_start) * fps)
                if absolute <= last_absolute:
                    self.stop.wait(0.005)
                    continue
                loop, target = divmod(absolute, total)
                if loop != last_loop:
                    if self.kind == "traffic":
                        for tracker in model.predictor.trackers:
                            tracker.reset()
                    rules.reset()
                    counts_window.clear()
                    previous_level, level_since = "UNKNOWN", None
                next_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                # Decode only up to the scheduled frame; large gaps seek, never queue.
                gap = target - next_frame
                if loop != last_loop or gap < 0 or gap > 6:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                else:
                    for _ in range(gap):
                        cap.grab()
                captured_at = time.monotonic()
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError(f"Video decode failed at frame {target}")
                self.frame_fix = self.gps.read(captured_at)
                source_frame = max(0, int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1)
                begin = time.perf_counter()
                if self.kind == "traffic":
                    result = model.track(frame, persist=True, tracker=tracker_name, **kwargs)[0]
                else:
                    result = model.predict(frame, **kwargs)[0]
                # Ultralytics returns xyxy in original image coordinates and measured inference timing.
                self.inference_ms = float(result.speed["inference"])
                predict_ms = (time.perf_counter() - begin) * 1000
                boxes = []
                counts = Counter()
                signal_candidates = []
                governing_signals = []
                height, width = frame.shape[:2]
                for box in result.boxes:
                    class_id = int(box.cls.item())
                    label, confidence = result.names[class_id], float(box.conf.item())
                    xyxy = box.xyxy[0].tolist()
                    track = int(box.id.item()) if box.id is not None else None
                    boxes.append({"class_name": label, "confidence": confidence, "track_id": track,
                                  "xyxy": xyxy})
                    if label in {"bicycle", "car", "motorcycle", "bus", "truck", "person"}:
                        counts[label] += 1
                    if self.kind == "traffic" and label == "traffic light":
                        x1, y1, x2, y2 = [int(x) for x in xyxy]
                        crop = frame[max(0,y1):min(height,y2), max(0,x1):min(width,x2)]
                        color, score = classify_light_color(crop)
                        candidate={"state":color.upper(), "color_score":score, "detector_confidence":confidence}
                        if color != "unknown":
                            signal_candidates.append(candidate)
                        if rules.accepts_signal(xyxy,width,height):
                            governing_signals.append(candidate)
                vehicle_count = sum(counts[n] for n in ("bicycle", "car", "motorcycle", "bus", "truck"))
                observed_states = {item["state"] for item in governing_signals}
                governing_signal = next(iter(observed_states)) if len(observed_states)==1 else "UNKNOWN"
                rule_events = rules.update(boxes, governing_signal, source_frame/fps, width, height) if self.kind=="traffic" else []
                annotated = result.plot(line_width=2, labels=True, boxes=True, conf=True)
                if self.kind=="road" and cfg.get("pothole_shading", True):
                    import numpy as np
                    overlay = annotated.copy()
                    for index, box in enumerate(boxes):
                        if box["class_name"].lower() != "pothole": continue
                        if result.masks is not None and index < len(result.masks.xy):
                            cv2.fillPoly(overlay, [result.masks.xy[index].astype(np.int32)], (0,190,255))
                        else:
                            x1,y1,x2,y2=map(int,box["xyxy"])
                            cv2.rectangle(overlay,(max(0,x1),max(0,y1)),(min(width-1,x2),min(height-1,y2)),(0,190,255),-1)
                    annotated = cv2.addWeighted(overlay,0.18,annotated,0.82,0)
                    cv2.putText(annotated,"Pothole ROI highlight | depth not measured",(10,height-12),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),1,cv2.LINE_AA)
                if self.kind=="traffic" and False:
                    for points in rules.history.values():
                        trail=[(int(point[0]*width),int(point[1]*height)) for _,point in points]
                        for a,b in zip(trail,trail[1:]): cv2.line(annotated,a,b,(220,190,0),2)
                    if rules.enabled:
                        a,b=rules.settings["stop_line"]
                        cv2.line(annotated,(int(a[0]*width),int(a[1]*height)),(int(b[0]*width),int(b[1]*height)),(0,0,255),2)
                school = nearest_school(self.frame_fix,self.schools,cfg.get("school_context",{}).get("radius_m",150))

                if annotated.shape[1] > cfg["display_width"]:
                    scale = cfg["display_width"] / annotated.shape[1]
                    annotated = cv2.resize(annotated, (cfg["display_width"], round(annotated.shape[0] * scale)))
                encoded_ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, cfg["jpeg_quality"]])
                if not encoded_ok:
                    raise RuntimeError("JPEG encoding failed")
                jpeg = encoded.tobytes()
                now = time.monotonic()
                samples.append(now)
                while len(samples) > 2 and now - samples[0] > 5:
                    samples.popleft()
                processed_fps = (len(samples) - 1) / (samples[-1] - samples[0]) if len(samples) > 1 else None
                signal_states = {s["state"] for s in signal_candidates}
                signal = next(iter(signal_states)) if len(signal_states) == 1 else "UNKNOWN"
                level, average = "UNKNOWN", None
                if self.kind == "traffic":
                    counts_window.append((now, vehicle_count))
                    while counts_window and now - counts_window[0][0] > cfg["congestion_window_seconds"]:
                        counts_window.popleft()
                    average = sum(n for _, n in counts_window) / len(counts_window)
                    level = congestion_level(average).upper()
                    if level != previous_level:
                        previous_level, level_since = level, now
                    if level in ("MEDIUM", "HIGH") and now - level_since >= cfg["congestion_hold_seconds"]:
                        event = self.event("TRAFFIC_CONGESTION", level, source_frame/fps, source_frame,
                            {"congestion_level": level, "average_vehicle_count": round(average,2),
                             "counts": dict(counts), "method": "vehicle-count heuristic; not measured road speed",
                             "thresholds": {"low_max": cfg["congestion_low_max"], "medium_max": cfg["congestion_medium_max"]}},
                            vehicle_count=vehicle_count, evidence=jpeg)
                        self.outbox.put(event, f"{cfg['bus_id']}:{self.camera_id}:congestion:{level}", cfg["congestion_cooldown_seconds"],
                                        spatial_radius_m=cfg.get("congestion_radius_m",30), spatial_ttl_seconds=cfg.get("congestion_location_cooldown_seconds",120))
                    for rule_event in rule_events:
                        event = self.event(rule_event["event_type"],rule_event["severity"],source_frame/fps,source_frame,
                                           rule_event["metadata"],evidence=jpeg)
                        if event is not None:
                            event.update(track_id=rule_event["track_id"],vehicle_type=rule_event["vehicle_type"])
                            self.outbox.put(event, f"violation:{cfg['bus_id']}:{self.camera_id}:{rules.settings.get('video_sha256')}:{rule_event['track_id']}",86400)
                    if school and counts["person"]:
                        event=self.event("SCHOOL_ZONE_PEDESTRIAN", "MEDIUM",source_frame/fps,source_frame,
                            {"school":school,"person_count":counts["person"],"requires_review":True,
                             "method":"GPS school proximity plus person detection; not age or speeding inference"},evidence=jpeg)
                        self.outbox.put(event,f"school:{school['name']}",60,spatial_radius_m=100,spatial_ttl_seconds=300)
                else:
                    grouped = {}
                    for box in boxes:
                        grouped.setdefault(box["class_name"], []).append(box)
                    for label, observations in grouped.items():
                        if label.lower() not in cfg.get("road_event_classes",["pothole","crack","longitudinal_crack","transverse_crack","alligator_crack"]):
                            continue
                        # A supported class is an observation, never an invented depth/size/damage claim.
                        event = self.event("ROAD_OBSERVATION", "MEDIUM", source_frame/fps, source_frame,
                            {"class_name": label, "detections": observations,
                             "severity_basis": "prototype review priority; physical severity not estimated"},
                            confidence=max(b["confidence"] for b in observations), evidence=jpeg)
                        self.outbox.put(event, f"road:{label.lower()}", cfg["road_cooldown_seconds"],
                                        spatial_radius_m=cfg.get("road_dedup_radius_m",15),spatial_ttl_seconds=cfg.get("road_dedup_seconds",86400))
                with self.lock:
                    self.jpeg, self.published_at = jpeg, now
                    self.sequence += 1
                    self.state.update(inference_ms=self.inference_ms, prediction_wall_ms=predict_ms,
                        processed_fps=processed_fps, processing_latency_ms=(now-captured_at)*1000,
                        playback_lag_ms=max(0, (now-playback_start)-(loop*duration+source_frame/fps))*1000,
                        source_video_seconds=source_frame/fps, source_frame=source_frame,
                        skipped_frames=max(0, absolute-last_absolute-1), loop=loop,
                        vehicle_count=vehicle_count if self.kind == "traffic" else None,
                        counts=dict(counts), detection_count=len(boxes), detections=boxes,
                        congestion_level=level, average_vehicle_count=average,
                        signal_state=signal, signals=signal_candidates, governing_signal=governing_signal,
                        school_context=school, gps_source=self.frame_fix["source"], gps_error=self.frame_fix.get("error"),
                        updated_at=datetime.now(timezone.utc).isoformat())
                last_absolute, last_loop = absolute, loop
                self.stop.wait(max(0, 1/cfg["target_fps"] - (time.monotonic()-cycle)))
        except Exception as exc:
            LOG.exception("%s camera stopped", self.kind)
            with self.lock:
                self.state.update(status="error", error=str(exc))
        finally:
            if cap is not None:
                cap.release()


class EdgeRuntime:
    def __init__(self):
        self.config = load_config()
        self.started = time.monotonic()
        self.outbox = Outbox(BASE / "data" / "edge-outbox.sqlite3", self.config["central_url"])
        self.gps = GPSProvider(self.config, BASE, self.started, route_position)
        self.workers = {kind: CameraWorker(kind, self.config, self.outbox, self.started, self.gps)
                        for kind in ("road", "traffic")}
        self.sync_thread = threading.Thread(target=self.outbox.run, name="event-sync", daemon=True)

    def start(self):
        try:
            import cv2
            import torch
            cv2.setNumThreads(1)
            torch.set_num_threads(self.config["cpu_threads"])
        except ImportError:
            pass  # Workers publish the concrete dependency failure independently.
        self.sync_thread.start()
        for worker in self.workers.values():
            worker.thread.start()

    def close(self):
        self.outbox.stop.set()
        for worker in self.workers.values():
            worker.stop.set()
        for worker in self.workers.values():
            worker.thread.join(timeout=8)
        self.sync_thread.join(timeout=6)

    def status(self):
        return {"bus_id": self.config["bus_id"], "gps": self.gps.read(), "outbox": self.outbox.status(),
                "cameras": {kind: worker.snapshot() for kind, worker in self.workers.items()}}
