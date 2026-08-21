import { useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import toast from "react-hot-toast";
import * as turf from "@turf/turf";
import {
  updateFeature,
  deleteFeature,
  toggleFeatureVisible,
  moveFeature,
  setBackendGeoJson,
  clearBackendGeoJson,
  selectFeature,
} from "@/state/layersSlice.js";
import { BACKEND_ENABLED } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";

export function useFeatureActions(loadLayersFromBackend) {
  const dispatch = useDispatch();
  const items = useSelector((s) => s.layers.items);
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const selectFeatureById = useCallback(
    (backendId) => {
      dispatch(selectFeature(backendId));
    },
    [dispatch]
  );

  const renameFeature = useCallback(
    async (layerLocalId, featureLocalId, backendId, name) => {
      const normalizedName = name.toLowerCase().trim();
      const targetLayer = items.find((l) => l.localId === layerLocalId);
      if (targetLayer) {
        const duplicateExists = targetLayer.features?.some(
          (f) => f.localId !== featureLocalId && f.name?.toLowerCase().trim() === normalizedName
        );
        if (duplicateExists) {
          toast.error(`Feature name "${name}" already exists in this layer.`);
          return;
        }
      }

      dispatch(updateFeature({ layerLocalId, featureLocalId, changes: { name } }));
      if (BACKEND_ENABLED && backendId) {
        try {
          const targetLayer = items.find((l) => l.localId === layerLocalId);
          const layerId = targetLayer?.backendId;

          // Resolve case ID dynamically
          const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
          const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : activeCaseIdFromStore;

          const featureData = targetLayer?.features.find((f) => f.localId === featureLocalId);

          if (featureData && layerId) {
            let geometryForBackend = { ...featureData.geometry };
            let center = undefined;
            let radius = undefined;

            const isCircle = featureData.type === "circle";

            if (isCircle && geometryForBackend.type === "Point") {
              const geomCenter = featureData.center || featureData.properties?.center || geometryForBackend.center;
              const geomRadius = featureData.radius || featureData.properties?.radius || geometryForBackend.radius;

              if (geomCenter) {
                center = {
                  lat: parseFloat(geomCenter.lat),
                  lng: parseFloat(geomCenter.lng),
                };
              }
              if (geomRadius) {
                radius = parseFloat(geomRadius);
              }

              if (!center && geometryForBackend.coordinates && typeof geometryForBackend.coordinates[0] === "number") {
                const [lng, lat] = geometryForBackend.coordinates;
                center = { lat, lng };
              }

              if (center && radius != null) {
                const centerLngLat = [center.lng, center.lat];
                const turfCircle = turf.circle(centerLngLat, radius, { units: 'meters', steps: 64 });
                geometryForBackend = turfCircle.geometry;
              }
            } else {
              if (geometryForBackend.center) {
                delete geometryForBackend.center;
              }
              if (geometryForBackend.radius) {
                delete geometryForBackend.radius;
              }
            }

            const payload = {
              name: name,
              layer_id: layerId,
              case_id: resolvedCaseId,
              created_by: 1,
              geometry: geometryForBackend,
              geometry_type: isCircle ? "Polygon" : (featureData.type
                ? featureData.type.charAt(0).toUpperCase() + featureData.type.slice(1)
                : "Polygon"),
              properties: featureData.properties || {},
              ...(center && { center }),
              ...(radius && { radius }),
            };

            await layerService.editFeatureInLayer(resolvedCaseId, layerId, backendId, payload);
            await loadLayersFromBackend();
          }
        } catch (err) {
          console.error("[renameFeature]", err);
        }
      }
    },
    [dispatch, loadLayersFromBackend, items, activeCaseIdFromStore]
  );

  const removeFeature = useCallback(
    async (layerLocalId, featureLocalId, backendId) => {
      dispatch(deleteFeature({ layerLocalId, featureLocalId }));
      if (BACKEND_ENABLED && backendId) {
        try {
          const targetLayer = items.find((l) => l.localId === layerLocalId);
          const layerId = targetLayer?.backendId || 16;
          const res = await layerService.deleteFeature(activeCaseId, layerId, backendId);
          toast.success(res?.message || res?.detail || "Feature deleted successfully");
        } catch (err) {
          console.error("[removeFeature]", err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Failed to delete feature");
        }
      } else {
        toast.success("Feature deleted successfully");
      }
    },
    [dispatch, items, activeCaseId]
  );

  const toggleFeatureVis = useCallback(
    async (layerLocalId, featureLocalId) => {
      const fromLayer = items.find((l) => l.localId === layerLocalId);
      const featureData = fromLayer?.features.find((f) => f.localId === featureLocalId);
      if (!featureData) return;

      const newVisible = !featureData.visible;
      dispatch(toggleFeatureVisible({ layerLocalId, featureLocalId }));

      if (BACKEND_ENABLED && featureData.backendId && fromLayer.backendId) {
        try {
          const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
          const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : activeCaseIdFromStore;

          await layerService.editFeaturePartialInLayer(
            resolvedCaseId,
            fromLayer.backendId,
            featureData.backendId,
            {
              properties: {
                ...(featureData.properties || {}),
                visible: newVisible,
              },
            }
          );
        } catch (err) {
          console.error("[toggleFeatureVis]", err);
        }
      }
    },
    [dispatch, items, activeCaseIdFromStore]
  );

  const dragFeature = useCallback(
    async (
      featureLocalId,
      fromLayerLocalId,
      toLayerLocalId,
      featureBackendId,
      toLayerBackendId
    ) => {
      const fromLayer = items.find((l) => l.localId === fromLayerLocalId);
      const featureData = fromLayer?.features.find((f) => f.localId === featureLocalId);

      dispatch(moveFeature({ featureLocalId, fromLayerLocalId, toLayerLocalId }));

      const fromLayerBackendId = fromLayer?.backendId;

      // Resolve case ID dynamically
      const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
      const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : activeCaseIdFromStore;

      if (BACKEND_ENABLED && featureBackendId && fromLayerBackendId && toLayerBackendId && featureData) {
        try {
          const res = await layerService.editFeaturePartialInLayer(
            resolvedCaseId,
            fromLayerBackendId, // Use source layer ID in the path
            featureBackendId,
            { layer_id: toLayerBackendId }
          );
          toast.success(res?.message || res?.detail || "Feature moved successfully");
          await loadLayersFromBackend();
        } catch (err) {
          console.error("[dragFeature]", err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Failed to move feature");
          await loadLayersFromBackend();
        }
      }
    },
    [dispatch, loadLayersFromBackend, items, activeCaseIdFromStore]
  );

  const saveGeoJsonToBackend = useCallback(
    async (geojson, fileName = "Uploaded File", layerName = "Uploaded Data") => {
      if (!BACKEND_ENABLED || !geojson || !geojson.features) return;
      try {
        // Resolve case ID dynamically
        const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
        const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : activeCaseIdFromStore;

        let backendLayerId = null;
        const existingLayer = items.find((l) => l.name === layerName);

        if (existingLayer && existingLayer.backendId) {
          backendLayerId = existingLayer.backendId;
        } else {
          const layerRes = await layerService.createLayer({
            case_id: resolvedCaseId,
            name: layerName,
            layer_type: "group",
            visible: true,
            opacity: 1,
            color: "#000000",
          });
          backendLayerId = layerRes.id;
        }

        const flattenCoordinates = (coords) => {
          if (Array.isArray(coords)) {
            if (typeof coords[0] === "number") {
              return coords.slice(0, 2);
            }
            return coords.map(flattenCoordinates);
          }
          return coords;
        };

        const geometries = [];
        for (const f of geojson.features) {
          if (f.geometry && f.geometry.coordinates) {
            f.geometry.coordinates = flattenCoordinates(f.geometry.coordinates);
            geometries.push(f.geometry);
          }
        }

        const multiGeometry = {
          type: "GeometryCollection",
          geometries: geometries,
        };

        const res = await layerService.createFeature({
          name: fileName,
          layer_id: backendLayerId,
          case_id: resolvedCaseId,
          created_by: 1,
          geometry: multiGeometry,
          geometry_type: "GeometryCollection",
          properties: { name: fileName },
        });

        toast.success(res?.message || res?.detail || `${fileName} saved to backend!`);
        await loadLayersFromBackend();
      } catch (err) {
        console.error("[saveGeoJsonToBackend] error:", err);
        toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Failed to save uploaded features to backend.");
      }
    },
    [loadLayersFromBackend, items, activeCaseIdFromStore]
  );

  const setBackendGeoJsonData = useCallback(
    (geojson) => {
      dispatch(setBackendGeoJson(geojson));
    },
    [dispatch]
  );

  const clearBackendGeoJsonData = useCallback(() => {
    dispatch(clearBackendGeoJson());
  }, [dispatch]);

  return {
    selectFeatureById,
    renameFeature,
    removeFeature,
    toggleFeatureVis,
    dragFeature,
    saveGeoJsonToBackend,
    setBackendGeoJsonData,
    clearBackendGeoJsonData,
  };
}
