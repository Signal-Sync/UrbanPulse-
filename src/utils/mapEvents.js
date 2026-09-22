export function selectMapEvents(events, { now = Date.now(), minutes = 1440, includeSamples = false, category = 'ALL' } = {}) {
  const seen = new Set();
  return events.filter(event => {
    if (!Number.isFinite(event.lat) || !Number.isFinite(event.lng) || Math.abs(event.lat) > 90 || Math.abs(event.lng) > 180) return false;
    const fromModel = event.edgeEvent === true && ['CAMERA_AI', 'PRERECORDED_VIDEO_AI'].includes(event.detectionSource);
    if (!includeSamples && !fromModel) return false;
    const stamp = Date.parse(event.timestamp || event.detectedAt);
    if (minutes > 0 && (!Number.isFinite(stamp) || stamp > now + 5000 || now - stamp > minutes * 60000)) return false;
    if (category === 'POTHOLES' && !['pothole', 'road_damage'].includes(event.type)) return false;
    if (category === 'CONGESTION' && event.type !== 'traffic_congestion') return false;
    if (category === 'WATERLOGGING' && event.type !== 'waterlogging') return false;
    if (category === 'INCIDENTS' && !['red_light_violation', 'wrong_way_driving', 'school_zone_pedestrian', 'hit_and_run', 'rash_driving', 'dangerous_overtaking', 'school_zone_violation'].includes(event.type)) return false;
    if (seen.has(event.id)) return false;
    seen.add(event.id);
    return true;
  });
}
