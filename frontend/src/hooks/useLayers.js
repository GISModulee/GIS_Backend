import { useSelector } from "react-redux";
import { useLayerBootstrap } from "./useLayerBootstrap.js";
import { useLayerDrawing } from "./useLayerDrawing.js";
import { useLayerActions } from "./useLayerActions.js";
import { useFeatureActions } from "./useFeatureActions.js";

export function useLayers() {
  const items = useSelector((s) => s.layers.items);
  const selectedLayerId = useSelector((s) => s.layers.selectedLayerId);
  const pendingGeometry = useSelector((s) => s.layers.pendingGeometry);
  const pendingType = useSelector((s) => s.layers.pendingType);
  const pendingColor = useSelector((s) => s.layers.pendingColor);
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);
  const hoveredFeatureId = useSelector((s) => s.layers.hoveredFeatureId);
  const resultLayers = useSelector((s) => s.layers.resultLayers);

  const { loadLayersFromBackend } = useLayerBootstrap();
  const { holdDrawnShape, cancelDrawing, saveShape } = useLayerDrawing();
  const layerActions = useLayerActions();
  const featureActions = useFeatureActions(loadLayersFromBackend);

  return {
    items,
    resultLayers,
    selectedLayerId,
    pendingGeometry,
    pendingType,
    pendingColor,
    selectedFeatureId,
    hoveredFeatureId,
    loadLayersFromBackend,
    holdDrawnShape,
    cancelDrawing,
    saveShape,
    ...layerActions,
    ...featureActions,
  };
}