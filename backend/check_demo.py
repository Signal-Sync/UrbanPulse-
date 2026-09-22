"""Read-only checks of running UrbanPulse services. No synthetic events are sent."""
import argparse
import json
import math
import statistics
import time
from urllib.request import urlopen


def read(url):
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def evaluate(samples, events):
    failures, warnings, cameras = [], [], {}
    for kind in ('road', 'traffic'):
        states = [s.get('cameras', {}).get(kind, {}) for s in samples]
        last = states[-1]
        names = last.get('classes', {})
        names = list(names.values()) if isinstance(names, dict) else names
        if any(s.get('status') != 'running' for s in states):
            failures.append(f'{kind}: not running throughout sample; {last.get("error")}')
        if len({s.get('updated_at') for s in states}) < 2:
            failures.append(f'{kind}: no new processed frame observed')
        if kind == 'road' and not any('pothole' in str(n).lower() for n in names):
            failures.append('Road model does not report a pothole class')
        if kind == 'traffic' and not any(str(n).lower() in ('car', 'bus', 'truck', 'motorcycle') for n in names):
            failures.append('Traffic model does not report expected vehicle classes')
        metrics = {}
        for key in ('inference_ms', 'processed_fps', 'frame_age_ms'):
            values = [s.get(key) for s in states]
            values = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
            metrics[key + '_median'] = round(statistics.median(values), 2) if values else None
        if not metrics['processed_fps_median'] or metrics['processed_fps_median'] <= 0:
            failures.append(f'{kind}: no positive processed FPS reported')
        cameras[kind] = dict(classes=names, device=last.get('device'), **metrics)
    if not samples[-1].get('gps', {}).get('valid'):
        failures.append('GPS unavailable: geolocated event generation is paused')
    for kind in ('ROAD_OBSERVATION', 'TRAFFIC_CONGESTION'):
        found = [e for e in events if e.get('event_type') == kind and e.get('source') in ('PRERECORDED_VIDEO_AI', 'CAMERA_AI')]
        if not found:
            warnings.append(f'No {kind} found in received history. Demonstrate a qualifying condition; do not force a false event.')
        for event in found:
            for field in ('event_id', 'timestamp', 'bus_id', 'camera_id', 'gps_source'):
                if not event.get(field):
                    failures.append(f'{kind}: missing {field}')
            for field, maximum in (('latitude', 90), ('longitude', 180)):
                v = event.get(field)
                if not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > maximum:
                    failures.append(f'{kind}: invalid {field}')
    return dict(result='FAIL' if failures else 'CHECKS_PASSED_WITH_WARNINGS' if warnings else 'PIPELINE_CHECKS_PASSED',
                failures=failures, warnings=warnings, cameras=cameras,
                outbox=samples[-1].get('outbox'), gps=samples[-1].get('gps'),
                received_events_examined=len(events),
                limitation='Reported timings are sampled telemetry, not an accuracy benchmark. Received events may be historical. Visually check boxes, notifications and map placement.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--edge', default='http://127.0.0.1:8001')
    p.add_argument('--central', default='http://127.0.0.1:8000')
    p.add_argument('--samples', type=int, default=6)
    args = p.parse_args()
    if args.samples < 2:
        p.error('--samples must be at least 2')
    try:
        samples = []
        for i in range(args.samples):
            samples.append(read(args.edge.rstrip('/') + '/api/status'))
            if i + 1 < args.samples:
                time.sleep(2)
        events, cursor = [], 0
        for _ in range(50):
            page = read(f'{args.central.rstrip("/")}/api/events?after={cursor}&limit=200')
            events.extend(page['events'])
            if len(page['events']) < 200 or page['next_cursor'] == cursor:
                break
            cursor = page['next_cursor']
        result = evaluate(samples, events)
        print(json.dumps(result, indent=2))
        return 1 if result['failures'] else 0
    except Exception as exc:
        print(json.dumps({'result': 'FAIL', 'error': str(exc), 'action': 'Start both services and run this check again.'}, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
