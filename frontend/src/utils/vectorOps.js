import * as turf from '@turf/turf';

export function featureToPolygon(f) {
  if (!f) return null;

  let featureObj = f;
  if (typeof featureObj === "string") {
    try {
      featureObj = JSON.parse(featureObj);
    } catch (_) {
      return null;
    }
  }

  let geom = featureObj.geometry;
  if (!geom) return null;

  if (typeof geom === "string") {
    try {
      geom = JSON.parse(geom);
    } catch (_) {
      return null;
    }
  }

  if (!geom.coordinates || !Array.isArray(geom.coordinates) || geom.coordinates.length === 0) {
    return null;
  }

  let properties = featureObj.properties || {};
  if (typeof properties === "string") {
    try {
      properties = JSON.parse(properties);
    } catch (_) { }
  }

  const type = geom.type;
  const isCircle = String(featureObj.type || "").toLowerCase() === 'circle' ||
    String(featureObj.geometry_type || "").toLowerCase() === 'circle' ||
    properties?.radius !== undefined ||
    geom.radius !== undefined;

  if (isCircle) {
    const coords = geom.coordinates;
    const radius = properties?.radius || geom.radius || 100;
    return turf.circle(coords, radius, { units: 'meters' });
  }

  if (type === 'Polygon' || type === 'MultiPolygon') {
    return turf.feature(geom);
  }

  if (type === 'Point') {
    return turf.buffer(turf.feature(geom), 1, { units: 'meters' });
  }

  if (type === 'LineString' || type === 'MultiLineString') {
    return turf.buffer(turf.feature(geom), 1, { units: 'meters' });
  }

  return null;
}

export function doFeaturesIntersect(featA, featB) {
  try {
    const geomA = featureToPolygon(featA);
    const geomB = featureToPolygon(featB);
    if (!geomA || !geomB) return false;

    let inter = null;
    try {
      inter = turf.intersect(turf.featureCollection([geomA, geomB]));
    } catch (_) {
      try {
        inter = turf.intersect(geomA, geomB);
      } catch (_) {}
    }
    return inter !== null;
  } catch (_) {
    return false;
  }
}

export function runVectorOp(featA, featB, operation) {
  const geomA = featureToPolygon(featA);
  const geomB = featureToPolygon(featB);

  if (!geomA || !geomB) {
    throw new Error("Selected features must have valid geometries.");
  }

  switch (operation) {
    case 'union':
      try {
        return turf.union(turf.featureCollection([geomA, geomB]));
      } catch (_) {
        return turf.union(geomA, geomB);
      }
    case 'intersection':
      try {
        return turf.intersect(turf.featureCollection([geomA, geomB]));
      } catch (_) {
        return turf.intersect(geomA, geomB);
      }
    case 'difference':
      try {
        return turf.difference(turf.featureCollection([geomA, geomB]));
      } catch (_) {
        return turf.difference(geomA, geomB);
      }
    default:
      throw new Error(`Unknown operation: ${operation}`);
  }
}
