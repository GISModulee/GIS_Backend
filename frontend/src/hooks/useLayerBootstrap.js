import { useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import { hydrateFromBackend } from "@/state/layersSlice.js";
import { BACKEND_ENABLED } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";

export function useLayerBootstrap() {
  const dispatch = useDispatch();
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);

  const loadLayersFromBackend = useCallback(async () => {
    if (!BACKEND_ENABLED) return;
    try {
      const match = window.location.pathname.match(/\/map\/(\d+)/);
      const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

      const layers = await layerService.getAllForCase(activeCaseId);
      console.log("[loadLayersFromBackend] layers:", layers);

      const hydrated = [];
      for (const layer of layers) {
        const layerLocalId = `local_${layer.id}`;
        const isGeoclipLayer = layer.layer_type === "geoclip";

        let featuresList = [];
        try {
          const res = isGeoclipLayer
            ? await layerService.getGeoclipFeatures(layer.id)
            : await layerService.getFeaturesByLayer(activeCaseId, layer.id);
          if (Array.isArray(res)) {
            featuresList = res;
          } else if (res && Array.isArray(res.features)) {
            featuresList = res.features;
          } else if (res && Array.isArray(res.data)) {
            featuresList = res.data;
          }
        } catch (err) {
          console.warn(`[Bootstrap] Failed to fetch layer features for layer ${layer.id}:`, err);
        }

        const isImagePredictionLayer = isGeoclipLayer || (layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name));

        const features = [];
        for (let index = 0; index < featuresList.length; index++) {
          const rawItem = featuresList[index];
          const toInt = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) && n > 0 ? n : null; };
          const initialFeatureNumber =
            toInt(rawItem.feature_number) ??
            toInt(rawItem.properties?.feature_number) ??
            toInt(rawItem.id) ??
            (index + 1);

          let f = rawItem;
          // Skip per-feature detail fetch for geoclip layers — they use a different API path
          if (!isGeoclipLayer) {
            try {
              const singleRes = await layerService.getSingleFeature(activeCaseId, layer.id, initialFeatureNumber);
              if (singleRes && typeof singleRes === "object") {
                f = { ...rawItem, ...singleRes };
              }
            } catch (err) {
              console.warn(`[Bootstrap] Failed to fetch single feature ${initialFeatureNumber} for layer ${layer.id}:`, err);
            }
          }

          let geometry = f.geometry;
          if (typeof geometry === "string") {
            try {
              geometry = JSON.parse(geometry);
            } catch (_) { }
          }

          let properties = f.properties ?? {};
          if (typeof properties === "string") {
            try {
              properties = JSON.parse(properties);
            } catch (_) { }
          }

          // Swap coordinate order if backend returned [latitude, longitude] (out of bounds for India)
          if (geometry?.type === "Point" && Array.isArray(geometry.coordinates) && geometry.coordinates.length === 2) {
            const [c0, c1] = geometry.coordinates;
            // If c0 is in latitude range [5, 40] and c1 is in longitude range [60, 100], it is swapped
            if (c0 >= 5 && c0 <= 40 && c1 >= 60 && c1 <= 100) {
              geometry = {
                ...geometry,
                coordinates: [c1, c0],
              };
            }
          }

          const isCircleFeature =
            f.geometry_type === "Circle" || properties?.type === "circle";

          if (isCircleFeature && geometry?.type === "Point") {
            geometry = {
              ...geometry,
              radius: f.radius || properties?.radius || 1000,
            };
          }

          const resolvedFeatureNumber =
            toInt(f.feature_number) ??
            toInt(f.properties?.feature_number) ??
            toInt(f.id) ??
            initialFeatureNumber;

          features.push({
            localId: `local_feat_${f.id || initialFeatureNumber}`,
            backendId: f.id || initialFeatureNumber,
            feature_number: resolvedFeatureNumber,
            case_id: f.case_id || activeCaseId,
            layer_id: f.layer_id || layer.id,
            layerLocalId,
            status: "saved",
            name: f.name || "Untitled Feature",
            type: isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon")),
            geometry_type: f.geometry_type,
            center: f.center || properties?.center,
            radius: f.radius || properties?.radius,
            geometry: geometry,
            properties: properties,
            color: properties?.color ?? f.color ?? layer.color ?? "#2563eb",
            category: properties?.category ?? f.category ?? "",
            visible: isImagePredictionLayer ? (index < 5) : true,
            error: null,
            commentsList: Array.isArray(f.comments) ? f.comments : (Array.isArray(f.commentsList) ? f.commentsList : []),
            comments_count: typeof f.comments_count === "number" ? f.comments_count : (Array.isArray(f.comments) ? f.comments.length : 0),
            hasComments: (typeof f.comments_count === "number" && f.comments_count > 0) || (Array.isArray(f.comments) && f.comments.length > 0) || (Array.isArray(f.commentsList) && f.commentsList.length > 0),
          });
        }

        hydrated.push({
          localId: layerLocalId,
          backendId: layer.id,
          case_id: layer.case_id || activeCaseId,
          status: "saved",
          name: layer.name || "null",
          type: layer.layer_type || "auto",
          visible: layer.visible ?? true,
          color: layer.color || "#2563eb",
          expanded: true,
          error: null,
          features,
        });
      }

      dispatch(hydrateFromBackend(hydrated));
    } catch (err) {
      console.error("[loadLayersFromBackend] Failed to load layers:", err);
    }
  }, [dispatch, activeCaseIdFromStore]);

  return { loadLayersFromBackend };
}
