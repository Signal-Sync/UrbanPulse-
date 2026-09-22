#!/usr/bin/env bash
# UrbanPulse — start all three services in a tmux session
SESSION="urbanpulse"

# Kill existing session if any
tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"

# Kill stale ports
sudo fuser -k 8000/tcp 8001/tcp 5173/tcp 2>/dev/null || true
sleep 1

# Backend window
tmux new-session -d -s "$SESSION" -n backend \
  "bash ~/Desktop/fleetbus/scripts/start-backend.sh"

# Edge window
tmux new-window -t "$SESSION" -n edge \
  "bash ~/Desktop/fleetbus/scripts/start-edge.sh"

# Frontend window
tmux new-window -t "$SESSION" -n frontend \
  "bash ~/Desktop/fleetbus/scripts/start-frontend.sh"

# Status window (auto-refresh every 5s)
tmux new-window -t "$SESSION" -n status \
  "while true; do clear; bash ~/Desktop/fleetbus/scripts/status.sh; sleep 5; done"

# Focus backend window
tmux select-window -t "$SESSION":backend

echo "═══════════════════════════════════════════════"
echo " UrbanPulse started in tmux session: $SESSION"
echo ""
echo "   Switch windows:   Ctrl+B  then  0/1/2/3"
echo "    0 = backend   1 = edge   2 = frontend   3 = status"
echo ""
echo "   Detach (keep running):  Ctrl+B  then  D"
echo "   Re-attach:              tmux attach -t $SESSION"
echo "   Kill everything:        tmux kill-session -t $SESSION"
echo "═══════════════════════════════════════════════"

# Attach to it
tmux attach -t "$SESSION"
