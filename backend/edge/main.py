"""Local demonstration previews.
Central service receives events, not these streams.
Now includes video upload + reset for per-camera live sources.
"""
import asyncio
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from edge.runtime import EdgeRuntime, load_config

runtime = None
_cfg = None
_video_paths = None
_backup_paths = None


def _init_paths():
    """Resolve the current video paths once at startup."""
    global _cfg, _video_paths, _backup_paths
    _cfg = load_config()
    _video_paths = {
        "road":    Path(_cfg["road_video"]).resolve(),
        "traffic": Path(_cfg["traffic_video"]).resolve(),
    }
    _backup_paths = {
        "road":    _video_paths["road"].with_suffix(".original.mp4"),
        "traffic": _video_paths["traffic"].with_suffix(".original.mp4"),
    }


def _ensure_backup(camera: str):
    """One-time backup of the original demo video so reset can restore it."""
    src = _video_paths[camera]
    bak = _backup_paths[camera]
    if not bak.exists() and src.exists():
        shutil.copy2(src, bak)


@asynccontextmanager
async def lifespan(app):
    global runtime
    _init_paths()
    runtime = EdgeRuntime()
    runtime.start()
    yield
    runtime.close()


app = FastAPI(title="UrbanPulse Bus Edge Preview", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (5173, 5174)
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/status")
def status():
    return runtime.status()


@app.get("/api/live/{camera}")
async def live(camera: str):
    worker = runtime.workers.get(camera)
    if worker is None:
        raise HTTPException(404, "Unknown camera")
    if worker.snapshot()["status"] == "error":
        raise HTTPException(503, worker.snapshot()["error"])

    async def frames():
        last = -1
        while not worker.stop.is_set():
            with worker.lock:
                jpeg, sequence = worker.jpeg, worker.sequence
                failed = worker.state["status"] == "error"
            if failed:
                break
            if jpeg is not None and sequence != last:
                last = sequence
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
                    + jpeg + b"\r\n"
                )
            await asyncio.sleep(0.04)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────
# Video source management
# ─────────────────────────────────────────────────────────────
@app.get("/api/camera-config")
def camera_config():
    """Show which video file each camera is currently pointed at."""
    out = {}
    for cam, path in _video_paths.items():
        out[cam] = {
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "has_backup": _backup_paths[cam].exists(),
        }
    return out

@app.post("/api/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    camera: str = Query("road", pattern="^(road|traffic)$"),
):
    """Replace the video used by the given camera.
    Returns {ok, filename, frames, fps} to match the frontend contract.
    """
    _ensure_backup(camera)
    target = _video_paths[camera]

    try:
        data = await file.read()
    except Exception as exc:
        return {"ok": False, "error": f"Failed to read upload: {exc}"}

    if len(data) < 1024:
        return {"ok": False, "error": "File too small to be a valid video"}

    tmp = target.with_suffix(".uploading")
    try:
        tmp.write_bytes(data)
        tmp.replace(target)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return {"ok": False, "error": f"Failed to save video: {exc}"}

    frames, fps = None, None
    try:
        import cv2
        cap = cv2.VideoCapture(str(target))
        if cap.isOpened():
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = round(float(cap.get(cv2.CAP_PROP_FPS)), 2)
        cap.release()
    except Exception:
        pass

    return {
        "ok": True,
        "camera": camera,
        "filename": file.filename or target.name,
        "bytes": len(data),
        "path": str(target),
        "frames": frames,
        "fps": fps,
    }

@app.post("/api/reset-video")
def reset_video(camera: str = Query(..., pattern="^(road|traffic)$")):
    """Restore the original demo video for the given camera."""
    bak = _backup_paths[camera]
    if not bak.exists():
        raise HTTPException(
            404, f"No backup exists for {camera}; nothing to reset to."
        )
    shutil.copy2(bak, _video_paths[camera])
    return {
        "reset": True,
        "camera": camera,
        "restored_from": str(bak),
        "path": str(_video_paths[camera]),
    }
