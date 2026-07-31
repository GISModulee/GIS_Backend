// ── Auto-sort by Area Helper ──────────────────────────────
export function calculateRoughArea(feature) {
  if (!feature || !feature.geometry) return 0;
  const geom = feature.geometry;

  // Circle area in square meters (check this BEFORE Point type, because circles are stored as Points!)
  if (geom.radius) return Math.PI * Math.pow(geom.radius, 2);

  if (
    geom.type === "Point" ||
    geom.type === "LineString" ||
    geom.type === "MultiLineString"
  )
    return 0;

  if (geom.type === "Polygon" && geom.coordinates && geom.coordinates[0]) {
    const ring = geom.coordinates[0];
    let area = 0;
    for (let i = 0; i < ring.length - 1; i++) {
      const p1 = ring[i];
      const p2 = ring[i + 1];
      area += (p2[0] - p1[0]) * (p2[1] + p1[1]);
    }
    const areaSqDegrees = Math.abs(area / 2);
    
    // Convert square degrees to approximate square meters
    // so polygons can be compared accurately with circles
    const lat = ring[0][1];
    const metersPerDegLat = 111320;
    const metersPerDegLon = 111320 * Math.cos(lat * (Math.PI / 180));
    
    return areaSqDegrees * metersPerDegLat * metersPerDegLon;
  }
  return 0;
}
