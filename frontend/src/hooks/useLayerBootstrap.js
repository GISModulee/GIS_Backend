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

      const hydrated = await Promise.all(
        layers.map(async (layer) => {
          const layerLocalId = `local_${layer.id}`;

          // Fetch features belonging to this layer
          let featuresList = [];
          try {
            const res = await layerService.getFeaturesByLayer(layer.id);
            if (Array.isArray(res)) {
              featuresList = res;
            } else if (res && Array.isArray(res.features)) {
              featuresList = res.features;
            } else if (res && Array.isArray(res.data)) {
              featuresList = res.data;
            }
          } catch (err) {
            console.error(`Failed to load features for layer ${layer.id}:`, err);
          }

          const isImagePredictionLayer = layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name);

          const features = await Promise.all(
            featuresList.map(async (f, index) => {
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

              let commentsList = [];
              try {
                commentsList = await layerService.getComments(f.id);
              } catch (_) {}

              return {
                localId: `local_feat_${f.id}`,
                backendId: f.id,
                layerLocalId,
                status: "saved",
                name: f.name || "Untitled Feature",
                type: isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon")),
                geometry: geometry,
                properties: properties,
                color: properties?.color ?? f.color ?? layer.color ?? "#2563eb",
                category: properties?.category ?? f.category ?? "",
                visible: isImagePredictionLayer ? (index < 5) : true,
                error: null,
                commentsList,
              };
            })
          );

          return {
            localId: layerLocalId,
            backendId: layer.id,
            status: "saved",
            name: layer.name || "null",
            type: layer.layer_type || "auto",
            visible: layer.visible ?? true,
            color: layer.color || "#2563eb",
            expanded: true,
            error: null,
            features,
          };
        })
      );

      dispatch(hydrateFromBackend(hydrated));
    } catch (err) {
      console.error("[loadLayersFromBackend] Failed to load layers:", err);
    }
  }, [dispatch, activeCaseIdFromStore]);

  return { loadLayersFromBackend };
}
