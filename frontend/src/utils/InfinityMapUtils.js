// src/utils/InfinityMapUtils.js

const shiftCoords = (coords, deltaLng) => {
  if (!coords) return;
  if (typeof coords[0] === "number" && typeof coords[1] === "number") {
    coords[0] += deltaLng;
  } else if (Array.isArray(coords)) {
    coords.forEach(c => shiftCoords(c, deltaLng));
  }
};

export const shiftGeometry = (geom, deltaLng) => {
  if (!geom) return null;
  const clone = JSON.parse(JSON.stringify(geom));
  shiftCoords(clone.coordinates, deltaLng);
  return clone;
};

export const shiftFeature = (feat, deltaLng) => {
  if (!feat) return null;
  const clone = JSON.parse(JSON.stringify(feat));
  if (clone.geometry) {
    clone.geometry = shiftGeometry(clone.geometry, deltaLng);
  }
  return clone;
};

export function replicateGeoJsonForInfinity(geojson) {
  if (!geojson) return geojson;

  let originalFeatures = [];
  if (geojson.type === "FeatureCollection") {
    originalFeatures = geojson.features || [];
  } else if (geojson.type === "Feature") {
    originalFeatures = [geojson];
  } else if (geojson.type === "GeometryCollection") {
    originalFeatures = (geojson.geometries || []).map(g => ({
      type: "Feature",
      geometry: g,
      properties: {}
    }));
  } else {
    originalFeatures = [{
      type: "Feature",
      geometry: geojson,
      properties: {}
    }];
  }

  const leftFeatures = originalFeatures.map(f => shiftFeature(f, -360)).filter(Boolean);
  const rightFeatures = originalFeatures.map(f => shiftFeature(f, 360)).filter(Boolean);

  return {
    type: "FeatureCollection",
    features: [...originalFeatures, ...leftFeatures, ...rightFeatures]
  };
}
