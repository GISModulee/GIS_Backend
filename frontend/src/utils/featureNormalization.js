import { addFeature, addFeaturesBatch, updateFeature } from "@/state/layersSlice.js";

export function normalizeFeature(f) {
  let geometry = f.geometry;
  if (typeof geometry === "string") {
    try {
      geometry = JSON.parse(geometry);
    } catch (_) {}
  }

  let properties = f.properties || {};
  if (typeof properties === "string") {
    try {
      properties = JSON.parse(properties);
    } catch (_) {}
  }

  // Swap coordinate order if backend returned [latitude, longitude] (out of bounds for India)
  if (geometry?.type === "Point" && Array.isArray(geometry.coordinates) && geometry.coordinates.length === 2) {
    const [c0, c1] = geometry.coordinates;
    if (c0 >= 5 && c0 <= 40 && c1 >= 60 && c1 <= 100) {
      geometry = {
        ...geometry,
        coordinates: [c1, c0],
      };
    }
  }

  const isCircleFeature = f.geometry_type === "Circle" || properties.type === "circle";
  if (isCircleFeature && geometry?.type === "Point") {
    geometry = {
      ...geometry,
      radius: f.radius || properties.radius || 1000,
    };
  }

  const type = isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

  return {
    localId: `local_feat_${f.id}`,
    backendId: f.id,
    feature_number: f.feature_number,
    case_id: f.case_id,
    layer_id: f.layer_id,
    status: "saved",
    name: f.name,
    type,
    geometry_type: f.geometry_type,
    center: f.center || properties.center,
    radius: f.radius || properties.radius,
    geometry: geometry,
    properties: properties,
    color: properties.color || f.color || "#2563eb",
    category: properties.category || f.category || "",
    commentsList: [],
    comments_count: 0,
    hasComments: false,
  };
}

export const dispatchFeatureCreated = (dispatch, layerLocalId, f) => {
  dispatch(addFeature({
    layerLocalId,
    featureData: normalizeFeature(f)
  }));
};

export const dispatchFeatureBatchCreated = (dispatch, layerLocalId, rawFeatures) => {
  if (!Array.isArray(rawFeatures)) return;

  const normalizedFeatures = rawFeatures.map((f) => normalizeFeature(f));

  dispatch(addFeaturesBatch({
    layerLocalId,
    featuresData: normalizedFeatures,
  }));
};

export const dispatchFeatureUpdated = (dispatch, layerLocalId, featureLocalId, f) => {
  const normalized = normalizeFeature(f);

  dispatch(updateFeature({
    layerLocalId,
    featureLocalId,
    changes: {
      name: normalized.name,
      type: normalized.type,
      geometry_type: normalized.geometry_type,
      center: normalized.center,
      radius: normalized.radius,
      geometry: normalized.geometry,
      properties: normalized.properties,
      color: normalized.color,
      category: normalized.category,
    }
  }));
};
