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
      const layer = items.find((l) => l.localId === localId);
      if (BACKEND_ENABLED && backendId && layer) {
        try {
          await layerService.updateLayer(activeCaseId, backendId, { name });
          dispatch(updateLayer({ localId, changes: { name } }));
        } catch (err) {
          console.error("[renameLayer]", err);
          toast.error(getErrorMessage(err));
        }
      } else {
        dispatch(updateLayer({ localId, changes: { name } }));
      }
    },
    [dispatch, items, activeCaseId]
  );

   const removeLayer = useCallback(
    async (localId, backendId) => {
      const layer = items.find((l) => l.localId === localId);
      const isGeoclipOrImageLayer =
        (layer && (layer.type === 'geoclip' || layer.type === 'geoclip_prediction')) ||
        (layer && layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name));

      if (BACKEND_ENABLED && isGeoclipOrImageLayer) {
        try {
          await layerService.deleteGeoclipLayer(layer.backendId || backendId);
          toast.success('Image layer deleted successfully');
        } catch (err) {
          console.error('[removeLayer][geoclip/image]', err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || 'Failed to delete image layer');
        }
        // Use dedicated geoclip/image deletion — skip the regular layer deletion flow
        dispatch(deleteLayer(localId));
        return;
      }

      // For regular layers: remove from Redux first for instant UI feedback,
      // then ask the backend to delete the layer (backend cascades feature deletion).
      dispatch(deleteLayer(localId));
      if (BACKEND_ENABLED && backendId) {
        try {
          const res = await layerService.deleteLayer(activeCaseId, backendId);
          toast.success(res?.message || res?.detail || "Layer deleted successfully");
        } catch (err) {
          console.error("[removeLayer]", err);
          toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Failed to delete layer");
        }
      } else {
        toast.success("Layer deleted successfully");
      }
    },
    [dispatch, items, activeCaseId]
  );


  const toggleVisible = useCallback(
    async (localId, backendId, current) => {
      dispatch(toggleLayerVisible(localId));
      if (BACKEND_ENABLED && backendId) {
        try {
          await layerService.updateLayer(activeCaseId, backendId, { visible: !current });
        } catch (err) {
          console.error("[toggleVisible]", err);
        }
      }
    },
    [dispatch, activeCaseId]
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
