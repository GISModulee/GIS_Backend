import { useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import toast from "react-hot-toast";
import {
  tempId,
  setLayerBackendId,
  setFeatureBackendId,
  setPendingGeometry,
  clearPendingGeometry,
  confirmSaveShape,
  deleteLayer,
} from "@/state/layersSlice.js";
import { BACKEND_ENABLED } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";
import { useLayerBootstrap } from "./useLayerBootstrap.js";

export function useLayerDrawing() {
  const dispatch = useDispatch();
  const { loadLayersFromBackend } = useLayerBootstrap();
  const items = useSelector((s) => s.layers.items);
  const selectedLayerId = useSelector((s) => s.layers.selectedLayerId);
  const pendingGeometry = useSelector((s) => s.layers.pendingGeometry);
  const pendingType = useSelector((s) => s.layers.pendingType);
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const holdDrawnShape = useCallback(
    (geometry, type, color) => {
      dispatch(setPendingGeometry({ geometry, type, color }));
    },
    [dispatch]
  );

  const cancelDrawing = useCallback(() => {
    dispatch(clearPendingGeometry());
  }, [dispatch]);

  const saveShape = useCallback(
    async ({ name, category, color }) => {
      const selectedLayer = items.find((l) => l.localId === selectedLayerId);

      if (selectedLayer) {
        const normalizedName = name.toLowerCase().trim();
        const duplicateFeatureExists = selectedLayer.features?.some(
          (f) => f.name?.toLowerCase().trim() === normalizedName
        );
        if (duplicateFeatureExists) {
          toast.error(`Feature name "${name}" already exists in this layer.`);
          return;
        }
      }

      const geometrySnapshot = pendingGeometry;
      const typeSnapshot = pendingType;
      const preFeatureLocalId = tempId();
      const preLayerLocalId = tempId();

      if (BACKEND_ENABLED) {
        try {
          let backendLayerId = selectedLayer?.backendId ?? null;

          const geometryForBackend = { ...geometrySnapshot };
          let center = undefined;
          let radius = undefined;
          const isCircle = typeSnapshot === "circle";

          if (geometryForBackend.center) {
            if (isCircle) {
              center = {
                lat: parseFloat(geometryForBackend.center.lat),
                lng: parseFloat(geometryForBackend.center.lng),
              };
            }
            delete geometryForBackend.center;
          }
          if (geometryForBackend.radius) {
            if (isCircle) {
              radius = parseFloat(geometryForBackend.radius);
            }
            delete geometryForBackend.radius;
          }

          // Resolve case ID dynamically at the moment of saving the shape
          const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
          const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : activeCaseIdFromStore;

          // 1. Call backend API first
          const featureRes = await layerService.createFeature({
            name,
            layer_id: backendLayerId,
            case_id: resolvedCaseId,
            created_by: 1,
            geometry: geometryForBackend,
            geometry_type: typeSnapshot
              ? typeSnapshot.charAt(0).toUpperCase() + typeSnapshot.slice(1)
              : "Polygon",
            properties: { name, type: typeSnapshot, color, category, radius, center },
            ...(center && { center }),
            ...(radius && { radius }),
          });

          // 2. Only if successful, confirm and add feature to local state (drawing it)
          dispatch(
            confirmSaveShape({ name, category, color, preFeatureLocalId, preLayerLocalId })
          );

          if (!backendLayerId && featureRes.layer_id) {
            backendLayerId = featureRes.layer_id;
            dispatch(
              setLayerBackendId({ localId: preLayerLocalId, backendId: backendLayerId })
            );
          }

          dispatch(
            setFeatureBackendId({
              layerLocalId: selectedLayer?.localId || preLayerLocalId,
              featureLocalId: preFeatureLocalId,
              backendId: featureRes.feature_id || featureRes.id,
              feature_number: featureRes.feature_number,
              case_id: featureRes.case_id || resolvedCaseId,
              layer_id: featureRes.layer_id || backendLayerId,
            })
          );

          // If the backend didn't return feature_number (flat /features endpoint),
          // fetch the layer features list to resolve it and update Redux.
          if (!featureRes.feature_number) {
            try {
              const resolvedLayerId = featureRes.layer_id || backendLayerId;
              const savedFeatureId = featureRes.feature_id || featureRes.id;
              const layerFeatures = await layerService.getFeaturesByLayer(resolvedCaseId, resolvedLayerId);
              const match = Array.isArray(layerFeatures)
                ? layerFeatures.find((lf) => Number(lf.id) === Number(savedFeatureId))
                : null;
              if (match?.feature_number) {
                dispatch(
                  setFeatureBackendId({
                    layerLocalId: selectedLayer?.localId || preLayerLocalId,
                    featureLocalId: preFeatureLocalId,
                    backendId: savedFeatureId,
                    feature_number: match.feature_number,
                    case_id: featureRes.case_id || resolvedCaseId,
                    layer_id: resolvedLayerId,
                  })
                );
              }
            } catch (lookupErr) {
              console.warn("[useLayerDrawing] Could not resolve feature_number after save:", lookupErr);
            }
          }

          if (selectedLayer && !selectedLayer.visible) {
            toast("Feature created successfully, but the active layer is hidden.", {
              icon: "⚠️",
              duration: 3000,
            });
          } else {
            toast.success(featureRes?.message || featureRes?.detail || "Feature created successfully", {
              duration: 3000,
            });
          }
          await loadLayersFromBackend();
          console.log("[saveShape] done", featureRes);
        } catch (err) {
          console.error("[saveShape] backend error:", err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Backend is not connected");

          // Clear pending geometry to cancel drawing and close modal since we failed
          dispatch(clearPendingGeometry());
        }
      } else {
        // Fallback for when backend is disabled entirely
        dispatch(
          confirmSaveShape({ name, category, color, preFeatureLocalId, preLayerLocalId })
        );
        if (selectedLayer && !selectedLayer.visible) {
          toast("Feature created successfully, but the active layer is hidden.", {
            icon: "⚠️",
            duration: 3000,
          });
        } else {
          toast.success("Feature created successfully", {
            duration: 3000,
          });
        }
      }
    },
    [dispatch, pendingGeometry, pendingType, selectedLayerId, items, activeCaseIdFromStore]
  );

  return { holdDrawnShape, cancelDrawing, saveShape };
}
