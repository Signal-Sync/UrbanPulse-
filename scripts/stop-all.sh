#!/usr/bin/env bash
# UrbanPulse — stop all three services
echo "[stop] killing processes on ports 8000 / 8001 / 5173"
sudo fuser -k 8000/tcp 8001/tcp 5173/tcp 2>/dev/null || true
sleep 1
echo "[stop] done. Ports free."
