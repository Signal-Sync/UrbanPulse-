"""Durable edge outbox; cooldown insertion and queueing share a transaction."""
import json
from edge.intelligence import distance_m
from contextlib import contextmanager
import sqlite3
import threading
import time
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler


class Outbox:
    def __init__(self, path, central_url):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.url = central_url.rstrip("/") + "/api/events"
        self.stop = threading.Event()
        self.error = None
        self.last_sync = None
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS pending (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS cooldowns (key TEXT PRIMARY KEY, until REAL NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS spatial_events (event_id TEXT PRIMARY KEY, scope TEXT, lat REAL, lon REAL, source TEXT, until REAL, observations INTEGER DEFAULT 1)")
            con.execute("CREATE INDEX IF NOT EXISTS spatial_scope ON spatial_events(scope,source,until)")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.execute("PRAGMA journal_mode=WAL")
        try:
            with con:
                yield con
        finally:
            con.close()

    def put(self, event, key, cooldown, spatial_radius_m=None, spatial_ttl_seconds=86400):
        if event is None:
            return False
        now = time.time()
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if spatial_radius_m is not None:
                source=event['gps_source']
                rows=con.execute("SELECT event_id,lat,lon FROM spatial_events WHERE scope=? AND source=? AND until>?",
                                 (key,source,now)).fetchall()
                for event_id,lat,lon in rows:
                    if distance_m(lat,lon,event['latitude'],event['longitude']) <= spatial_radius_m:
                        con.execute("UPDATE spatial_events SET observations=observations+1 WHERE event_id=?",(event_id,))
                        return False
                con.execute("INSERT INTO spatial_events(event_id,scope,lat,lon,source,until) VALUES(?,?,?,?,?,?)",
                            (event['event_id'],key,event['latitude'],event['longitude'],source,now+spatial_ttl_seconds))
                con.execute("DELETE FROM spatial_events WHERE until<?",(now,))
            row = con.execute("SELECT until FROM cooldowns WHERE key=?", (key,)).fetchone() if spatial_radius_m is None else None
            if row and row[0] > now:
                return False
            con.execute("INSERT INTO pending VALUES(?,?)", (event["event_id"], json.dumps(event)))
            con.execute("INSERT OR REPLACE INTO cooldowns VALUES(?,?)", (key, now + cooldown))
            con.execute("DELETE FROM cooldowns WHERE until<?", (now,))
        return True

    def status(self):
        with self.connect() as con:
            count = con.execute("SELECT COUNT(*) FROM pending").fetchone()[0]
        return {"pending_events": count, "last_sync": self.last_sync, "error": self.error}

    def sync_once(self, client=None):
        opener = client or build_opener(ProxyHandler({}))
        with self.connect() as con:
            rows = con.execute("SELECT id,payload FROM pending ORDER BY rowid LIMIT 20").fetchall()
        for event_id, payload in rows:
            request = Request(self.url, data=payload.encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=5) as response:
                ack = json.load(response)
            if not ack.get("accepted") or ack.get("event_id") != event_id:
                raise RuntimeError("Backend did not acknowledge this event")
            with self.connect() as con:
                con.execute("DELETE FROM pending WHERE id=?", (event_id,))
            self.last_sync = time.time()
        self.error = None

    def run(self):
        delay = 1
        client = build_opener(ProxyHandler({}))
        while not self.stop.is_set():
            try:
                self.sync_once(client)
                delay = 1
            except Exception as exc:
                self.error = str(exc)
                delay = min(delay * 2, 30)
            self.stop.wait(delay)
