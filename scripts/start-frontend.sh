#!/usr/bin/env bash
# UrbanPulse — Terminal 3: React Frontend (port 5173)
set -e

cd ~/Desktop/fleetbus

# Kill stale process on 5173 if any
if command -v fuser >/dev/null 2>&1; then
  fuser -k 5173/tcp 2>/dev/null || true
fi

echo "═══════════════════════════════════════════"
echo " UrbanPulse FRONTEND — port 5173"
echo " cwd: $(pwd)"
echo "═══════════════════════════════════════════"

# Install deps if node_modules missing
if [ ! -d node_modules ]; then
  echo "[setup] node_modules missing — running npm ci"
  npm ci
fi

exec npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
