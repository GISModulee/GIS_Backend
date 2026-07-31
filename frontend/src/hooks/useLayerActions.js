import { useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import toast from "react-hot-toast";
import {
  tempId,
  addLayer,
  updateLayer,
  deleteLayer,
  toggleLayerVisible,
  toggleLayerExpanded,
  selectLayer,
  setLayerBackendId,
} from "@/state/layersSlice.js";
import { BACKEND_ENABLED } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";
import { getErrorMessage } from "@/utils/ErrorUtils.js";

export function useLayerActions() {
  const dispatch = useDispatch();
  const items = useSelector((s) => s.layers.items);
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const createLayer = useCallback(
    async (opts = {}) => {
      const localId = tempId();
      dispatch(addLayer({ ...opts, localId }));

      if (BACKEND_ENABLED) {
        try {
          const res = await layerService.createLayer({
            case_id: activeCaseId,
            name: opts.name || "Auto Layer 1",
            layer_type: "auto",
            visible: true,
            opacity: 1,
            color: opts.color || "#2563eb",
          });
          dispatch(setLayerBackendId({ localId, backendId: res.id }));
        } catch (err) {
          console.error("[createLayer] backend error:", err);
          dispatch(deleteLayer(localId));
          toast.error(getErrorMessage(err));
        }
      }
    },
    [dispatch, activeCaseId]
  );

  const renameLayer = useCallback(
    async (localId, backendId, name) => {
      if (BACKEND_ENABLED && backendId) {
        try {
          await layerService.updateLayer(backendId, { name });
          dispatch(updateLayer({ localId, changes: { name } }));
        } catch (err) {
          console.error("[renameLayer]", err);
          toast.error(getErrorMessage(err));
        }
      } else {
        dispatch(updateLayer({ localId, changes: { name } }));
      }
    },
    [dispatch]
  );

  const removeLayer = useCallback(
    async (localId, backendId) => {
      const layer = items.find((l) => l.localId === localId);
      if (BACKEND_ENABLED && layer && layer.features) {
        for (const feature of layer.features) {
          if (feature.backendId) {
            try {
              await layerService.deleteFeature(feature.backendId);
            } catch (err) {
              console.error(
                `[removeLayer] Failed to delete feature ${feature.backendId}:`,
                err
              );
            }
          }
        }
      }

      dispatch(deleteLayer(localId));
      if (BACKEND_ENABLED && backendId) {
        try {
          const res = await layerService.deleteLayer(backendId);
          toast.success(res?.message || res?.detail || "Layer deleted successfully");
        } catch (err) {
          console.error("[removeLayer]", err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Failed to delete layer");
        }
      } else {
        toast.success("Layer deleted successfully");
      }
    },
    [dispatch, items]
  );

  const toggleVisible = useCallback(
    async (localId, backendId, current) => {
      dispatch(toggleLayerVisible(localId));
      if (BACKEND_ENABLED && backendId) {
        try {
          await layerService.updateLayer(backendId, { visible: !current });
        } catch (err) {
          console.error("[toggleVisible]", err);
        }
      }
    },
    [dispatch]
  );

  const expandLayer = useCallback(
    (localId) => {
      dispatch(toggleLayerExpanded(localId));
    },
    [dispatch]
  );

  const chooseLayer = useCallback(
    (localId) => {
      dispatch(selectLayer(localId));
    },
    [dispatch]
  );

  return {
    createLayer,
    renameLayer,
    removeLayer,
    toggleVisible,
    expandLayer,
    chooseLayer,
  };
}
