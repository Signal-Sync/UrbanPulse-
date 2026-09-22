#!/usr/bin/env bash
# UrbanPulse — quick health check of all three services
set +e

echo "─── Ports ───"
sudo lsof -i :8000 -i :8001 -i :5173 -sTCP:LISTEN 2>/dev/null || echo "(none listening)"

echo ""
echo "─── Backend :8000 ───"
curl -s --max-time 3 http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || echo "❌ backend not reachable"

echo ""
echo "─── Events ───"
curl -s --max-time 3 http://127.0.0.1:8000/api/events | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('events:', len(d.get('events',[])))" 2>/dev/null || echo "❌ events endpoint failed"

echo ""
echo "─── Edge :8001 ───"
curl -s --max-time 3 http://127.0.0.1:8001/api/status | \
  python3 -c "
import sys,json
d=json.load(sys.stdin)
for k,v in d.get('cameras',{}).items():
    print(f\"  {k}: status={v.get('status')} frames={v.get('source_frame')} count={v.get('vehicle_count')} school={v.get('school_context')}\")
" 2>/dev/null || echo "❌ edge not reachable"

echo ""
echo "─── Frontend :5173 ───"
curl -s --max-time 3 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5173/ 2>/dev/null || echo "❌ frontend not reachable"

echo ""
echo "─── ANPR endpoint ───"
curl -s --max-time 3 http://127.0.0.1:8000/api/incidents/anpr | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('anpr incidents:', d.get('count',0))" 2>/dev/null || echo "❌ anpr endpoint missing"

echo ""
echo "─── Bandwidth endpoint ───"
curl -s --max-time 3 http://127.0.0.1:8000/api/metrics/bandwidth | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('reduction ratio:', d.get('reduction_ratio'))" 2>/dev/null || echo "❌ bandwidth endpoint missing"
