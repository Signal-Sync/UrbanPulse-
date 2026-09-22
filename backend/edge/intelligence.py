"""Geospatial context and conservative fixed-camera rules; no new model dependencies."""
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(a)))


class GPSProvider:
    def __init__(self, config, base, started, simulate):
        self.config, self.base, self.started, self.simulate = config, Path(base), started, simulate

    def read(self, captured_at=None):
        settings = self.config.get('gps', {})
        mode = settings.get('mode', 'simulated')
        if mode == 'simulated':
            lat, lon = self.simulate(self.config, (captured_at or time.monotonic())-self.started)
            return {'latitude':lat,'longitude':lon,'source':'SIMULATED_ROUTE','valid':True,
                    'accuracy_m':None,'error':None}
        try:
            if mode != 'file':
                raise ValueError('GPS mode must be simulated or file')
            path = Path(settings.get('path', 'data/current_gps.json'))
            if not path.is_absolute(): path = self.base/path
            if path.stat().st_size > 8192: raise ValueError('GPS record exceeds size limit')
            fix = json.loads(path.read_text())
            lat, lon = float(fix['latitude']), float(fix['longitude'])
            if not -90 <= lat <= 90 or not -180 <= lon <= 180: raise ValueError('Invalid GPS coordinates')
            stamp = datetime.fromisoformat(str(fix['timestamp']).replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError('GPS timestamp needs timezone')
            age = (datetime.now(timezone.utc)-stamp).total_seconds()
            if age < -2 or age > settings.get('max_age_seconds',15): raise ValueError('GPS fix is stale or future-dated')
            accuracy = float(fix['accuracy_m']) if fix.get('accuracy_m') is not None else None
            if accuracy is not None and (not math.isfinite(accuracy) or accuracy < 0 or accuracy > settings.get('max_accuracy_m',50)):
                raise ValueError('GPS accuracy outside configured limit')
            return {'latitude':lat,'longitude':lon,'source':'EXTERNAL_GPS','timestamp':stamp.isoformat(),
                    'accuracy_m':accuracy,'age_seconds':age,'valid':True,'error':None}
        except Exception as exc:
            return {'latitude':None,'longitude':None,'source':'EXTERNAL_GPS','valid':False,'error':str(exc)}


def nearest_school(fix, schools, radius):
    if not fix.get('valid'): return None
    nearest, best = None, radius
    for school in schools:
        try:
            dist = distance_m(fix['latitude'],fix['longitude'],float(school['lat']),float(school['lon']))
            if dist <= best:
                best = dist
                nearest = {'name':school.get('name','School'),'distance_m':round(dist,1),
                           'latitude':float(school['lat']),'longitude':float(school['lon'])}
        except (KeyError,ValueError,TypeError):
            continue
    return nearest


class TrafficRules:
    """A calibrated fixed-camera crossing is a review event, not a legal finding."""
    def __init__(self, settings, video_path):
        self.settings = settings
        self.enabled = False
        self.reason = 'Fixed-camera violations are disabled; calibration required'
        self.history = {}
        self.reported = set()
        self.red_since = None
        if not settings.get('enabled',False): return
        try:
            if settings.get('camera_mode') != 'fixed': raise ValueError('Moving camera not supported by these rules')
            expected = settings.get('video_sha256')
            with open(video_path,'rb') as handle:
                actual = hashlib.file_digest(handle,'sha256').hexdigest()
            if not expected or expected != actual: raise ValueError('Calibration does not match video SHA256')
            line, roi = settings['stop_line'], settings['signal_roi']
            if len(line)!=2 or any(len(p)!=2 for p in line): raise ValueError('Stop line needs two points')
            if len(roi)!=4 or any(not 0<=v<=1 for p in line for v in p) or any(not 0<=v<=1 for v in roi):
                raise ValueError('Use normalized coordinates in [0,1]')
            if roi[0]>=roi[2] or roi[1]>=roi[3] or line[0]==line[1]: raise ValueError('Invalid ROI or line')
            if settings.get('approach_side') not in (-1,1): raise ValueError('approach_side must be -1 or 1')
            self.enabled = True
            self.reason = 'Calibrated fixed-camera review rule enabled'
        except Exception as exc:
            self.reason = str(exc)

    def reset(self):
        self.history.clear(); self.reported.clear(); self.red_since=None

    def accepts_signal(self, xyxy, width, height):
        if not self.enabled: return False
        cx,cy=(xyxy[0]+xyxy[2])/(2*width),(xyxy[1]+xyxy[3])/(2*height)
        a,b,c,d=self.settings['signal_roi']
        return a<=cx<=c and b<=cy<=d

    def update(self, boxes, signal, now, width, height):
        # Track history also drives visual trails when violation rules are disabled.
        red_before = self.red_since
        if signal != 'RED': self.red_since=None
        elif self.red_since is None: self.red_since=now
        active={box['track_id'] for box in boxes if box['track_id'] is not None}
        self.history={key:points for key,points in self.history.items() if now-points[-1][0]<2}
        # Keep dedup state bounded with the active tracking histories.
        self.reported.intersection_update(self.history.keys())
        events=[]
        for box in boxes:
            tid=box['track_id']
            if tid is None or box['class_name'] not in {'car','motorcycle','bus','truck','bicycle'}: continue
            x1,y1,x2,y2=box['xyxy']; point=((x1+x2)/(2*width), y2/height)
            points=self.history.setdefault(tid,deque(maxlen=24))
            points.append((now,point))
            if not self.enabled or tid in self.reported or len(points)<2: continue
            if signal!='RED' or red_before is None or now-red_before<self.settings.get('red_hold_seconds',0.5): continue
            a,b=self.settings['stop_line']; ax,ay=a; bx,by=b
            length=math.hypot(bx-ax,by-ay)
            side=lambda p: ((bx-ax)*(p[1]-ay)-(by-ay)*(p[0]-ax))/length
            direction=self.settings['approach_side']; margin=self.settings.get('line_margin',0.003)
            current_side=side(point)*direction
            previous=next(((t,p) for t,p in reversed(list(points)[:-1]) if side(p)*direction>margin),None)
            if previous is None or current_side>=-margin: continue
            then,prev=previous
            if now-then>self.settings.get('max_crossing_seconds',1.5) or then<red_before: continue
            sp,sc=side(prev),side(point)
            ratio=sp/(sp-sc)
            cross=(prev[0]+ratio*(point[0]-prev[0]),prev[1]+ratio*(point[1]-prev[1]))
            along=((cross[0]-ax)*(bx-ax)+(cross[1]-ay)*(by-ay))/(length*length)
            if not 0<=along<=1: continue
            self.reported.add(tid)
            events.append({'event_type':'RED_LIGHT_VIOLATION','severity':'HIGH','track_id':tid,
                           'vehicle_type':box['class_name'],'confidence':None,
                           'metadata':{'requires_review':True,'detector_confidence':box['confidence'],
                           'method':'fixed-camera tracked stop-line crossing during stable ROI RED',
                           'stop_line':self.settings['stop_line'],'signal_roi':self.settings['signal_roi']}})
        return events
