import hashlib,json,tempfile,time,unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from edge.intelligence import GPSProvider, TrafficRules, nearest_school
from edge.outbox import Outbox

class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_gps_valid_then_stale_no_fallback(self):
        provider=GPSProvider({'gps':{'mode':'file','path':'gps.json'}},self.root,time.monotonic(),lambda *_:(1,2))
        self.assertFalse(provider.read()['valid'])
        fix={'latitude':13.08,'longitude':80.27,'timestamp':datetime.now(timezone.utc).isoformat(),'accuracy_m':4}
        (self.root/'gps.json').write_text(json.dumps(fix))
        self.assertEqual(provider.read()['source'],'EXTERNAL_GPS'); self.assertTrue(provider.read()['valid'])
        fix['timestamp']=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat()
        (self.root/'gps.json').write_text(json.dumps(fix))
        self.assertFalse(provider.read()['valid']); self.assertIsNone(provider.read()['latitude'])
    def test_simulation_label_and_school_context(self):
        fix=GPSProvider({},self.root,time.monotonic(),lambda *_:(13,80)).read()
        self.assertEqual(fix['source'],'SIMULATED_ROUTE')
        self.assertIsNotNone(nearest_school(fix,[{'name':'fixture','lat':13,'lon':80}],150))
        self.assertIsNone(nearest_school(fix,[{'lat':14,'lon':80}],150))
    def event(self,lat=13,source='EXTERNAL_GPS'):
        return {'event_id':str(uuid4()),'latitude':lat,'longitude':80,'gps_source':source}
    def test_spatial_dedup_restart_class_and_distance(self):
        path=self.root/'out.sqlite'; box=Outbox(path,'http://127.0.0.1:9')
        self.assertTrue(box.put(self.event(),'road:pothole',30,15))
        box=Outbox(path,'http://127.0.0.1:9')
        self.assertFalse(box.put(self.event(13.00001),'road:pothole',30,15))
        self.assertTrue(box.put(self.event(),'road:crack',30,15))
        self.assertTrue(box.put(self.event(13.001),'road:pothole',30,15))
        self.assertTrue(box.put(self.event(source='SIMULATED_ROUTE'),'road:pothole',30,15))
        self.assertEqual(box.status()['pending_events'],4)
    def test_distinct_violators_same_gps_are_not_discarded(self):
        box=Outbox(self.root/'out.sqlite','http://127.0.0.1:9')
        self.assertTrue(box.put(self.event(),'violation:track1',30)); self.assertTrue(box.put(self.event(),'violation:track2',30))
        self.assertFalse(box.put(None,'missinggps',30))
    def rule(self,**overrides):
        video=self.root/'fixture.mp4';video.write_bytes(b'checksum fixture, not inference')
        settings={'enabled':True,'camera_mode':'fixed','video_sha256':hashlib.sha256(video.read_bytes()).hexdigest(),
                  'stop_line':[[.2,.5],[.8,.5]],'signal_roi':[0,0,.2,.2],'approach_side':-1,'red_hold_seconds':.5}
        settings.update(overrides);return TrafficRules(settings,video)
    def box(self,y,x=50):
        return [{'track_id':7,'class_name':'car','xyxy':[x-5,y-10,x+5,y],'confidence':.8}]
    def cross(self,rule,signal='RED',x=50):
        rule.update(self.box(40,x),signal,0,100,100); rule.update(self.box(45,x),signal,.6,100,100)
        return rule.update(self.box(60,x),signal,.9,100,100)
    def test_confirmed_crossing_and_track_dedup(self):
        rule=self.rule();events=self.cross(rule);self.assertEqual(len(events),1)
        self.assertTrue(events[0]['metadata']['requires_review']);self.assertIsNone(events[0]['confidence'])
        self.assertEqual(rule.update(self.box(70),'RED',1,100,100),[])
    def test_green_unknown_outside_line_and_moving_disabled(self):
        for signal in ('GREEN','UNKNOWN'): self.assertEqual(self.cross(self.rule(),signal),[])
        self.assertEqual(self.cross(self.rule(),x=95),[])
        self.assertFalse(self.rule(camera_mode='moving').enabled);self.assertFalse(self.rule(video_sha256='wrong').enabled)
    def test_red_after_crossing_is_not_a_violation(self):
        rule=self.rule();rule.update(self.box(40),'GREEN',0,100,100);rule.update(self.box(60),'RED',.2,100,100)
        self.assertEqual(rule.update(self.box(70),'RED',.9,100,100),[])
