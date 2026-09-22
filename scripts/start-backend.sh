#!/usr/bin/env bash
# UrbanPulse — Terminal 1: Central Backend (port 8000)
set -e

cd ~/Desktop/fleetbus
source .venv/bin/activate

# Kill stale process on 8000 if any
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
fi

echo "═══════════════════════════════════════════"
echo " UrbanPulse CENTRAL BACKEND — port 8000"
echo " cwd: $(pwd)"
echo " venv: $(which python)"
echo "═══════════════════════════════════════════"

exec python -m uvicorn app.main:app \
  --app-dir backend \
  --host 127.0.0.1 \
  --port 8000
