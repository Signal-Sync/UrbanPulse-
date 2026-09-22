#!/usr/bin/env bash
# UrbanPulse — Terminal 2: Edge AI Worker (port 8001)
set -e

cd ~/Desktop/fleetbus
source .venv/bin/activate

# Kill stale process on 8001 if any
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8001/tcp 2>/dev/null || true
fi

# Clear any stale env overrides from previous sessions
unset EDGE_CONFIG ROAD_MODEL ROAD_VIDEO TRAFFIC_MODEL TRAFFIC_VIDEO
unset TRAFFIC_CONFIDENCE TRAFFIC_IMGSZ

# Force CPU inference (your laptop has no working CUDA)
export AI_DEVICE=cpu

echo "═══════════════════════════════════════════"
echo " UrbanPulse EDGE AI — port 8001"
echo " cwd: $(pwd)"
echo " venv: $(which python)"
echo " AI_DEVICE=$AI_DEVICE"
echo "═══════════════════════════════════════════"

exec python -m uvicorn edge.main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port 8001
