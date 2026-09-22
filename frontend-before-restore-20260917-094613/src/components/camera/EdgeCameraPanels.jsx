import React, { useEffect, useState } from 'react';
import { EDGE_URL, readJson } from '../../services/edgeApi';

const metric = value => Number.isFinite(value) ? value.toFixed(1) : '—';

function CameraPanel({ kind, state, connected }) {
  const [retry, setRetry] = useState(0);
  const [streamFailed, setStreamFailed] = useState(false);
  const road = kind === 'road';
  const running = connected && state?.status === 'running';
  useEffect(() => { if (running) { setStreamFailed(false); setRetry(n => n + 1); } }, [running]);
  return (
    <section className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-subtle min-w-0">
      <div className="px-4 py-3 border-b border-slate-200 flex justify-between items-center gap-2">
        <div>
          <h2 className="text-sm font-extrabold text-slate-900">{road ? 'ROAD INTELLIGENCE' : 'TRAFFIC INTELLIGENCE'}</h2>
          <p className="text-xs text-slate-500">{state?.bus_id || 'Bus pending'} · {road ? 'FRONT_CAMERA' : 'TRAFFIC_CAMERA'}</p>
        </div>
        <span className="text-xs font-semibold text-blue-700">{connected ? state?.status || 'starting' : 'offline'}</span>
      </div>
      <div className="aspect-video bg-slate-950 flex items-center justify-center relative">
        {running && !streamFailed ? (
          <img key={retry} src={`${EDGE_URL}/api/live/${kind}?retry=${retry}`} alt={`${kind} camera with model annotations`}
            className="w-full h-full object-contain" onError={() => setStreamFailed(true)} />
        ) : (
          <div className="p-5 text-center text-sm text-slate-200 break-words">
            {state?.error || (streamFailed ? 'Preview disconnected.' : connected ? 'Camera is starting…' : 'Start the local edge service on port 8001.')}
          </div>
        )}
      </div>
      <div className="p-4 space-y-3 text-sm">
        {streamFailed && <button className="text-blue-700 underline" onClick={() => { setStreamFailed(false); setRetry(n => n + 1); }}>Reconnect preview</button>}
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-slate-600">
          <span>Inference <b>{metric(running ? state?.inference_ms : null)} ms</b></span>
          <span>Processed <b>{metric(running ? state?.processed_fps : null)} FPS</b></span>
          <span>Frame age <b>{metric(running ? state?.frame_age_ms : null)} ms</b></span>
        </div>
        {!road && <>
          <div className="flex flex-wrap gap-4 font-semibold text-slate-900">
            <span>Vehicles: {running ? state?.vehicle_count ?? '—' : '—'}</span>
            <span>Congestion: {running ? state?.congestion_level || 'UNKNOWN' : 'UNKNOWN'}</span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-600">
            {['car', 'motorcycle', 'bus', 'truck', 'bicycle', 'person'].map(name => <span key={name}>{name}: {running ? state?.counts?.[name] ?? 0 : '—'}</span>)}
          </div>
          <p className="text-xs text-slate-500">Congestion is a sustained count-based indicator, not measured road speed.</p>
        </>}
        {road && <p className="text-xs text-slate-600">Shading highlights a detection region; depth is not measured. Model classes: {Object.values(state?.classes || {}).join(', ') || 'Available after the road weights load.'}</p>}
        <p className="text-xs text-slate-500">{state?.model || 'Model pending'} · {state?.device || 'Device pending'}{state?.fp16 ? ' · FP16' : ''} · {state?.source === 'CAMERA_AI' ? 'Live ESP32 camera · latency shown excludes camera/Wi-Fi delay' : 'prerecorded camera simulation'}</p>
      </div>
    </section>
  );
}

export function EdgeCameraPanels() {
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let cancelled = false, timer;
    async function poll() {
      try {
        const data = await readJson(`${EDGE_URL}/api/status`);
        if (!cancelled) { setStatus(data); setConnected(true); }
      } catch { if (!cancelled) setConnected(false); }
      if (!cancelled) timer = setTimeout(poll, 1000);
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CameraPanel kind="road" state={status?.cameras?.road} connected={connected} />
        <CameraPanel kind="traffic" state={status?.cameras?.traffic} connected={connected} />
      </div>
      <p className="text-xs text-slate-500">
        Local edge previews · GPS: {connected && status?.gps?.valid ? `${status.gps.latitude.toFixed(5)}, ${status.gps.longitude.toFixed(5)} (${status.gps.source})` : 'unavailable — geolocated events paused'}
        {' · '}Unsent events: {status?.outbox?.pending_events ?? '—'}
        {status?.outbox?.error && ' · Central sync unavailable; events remain buffered locally.'}
      </p>
    </div>
  );
}
