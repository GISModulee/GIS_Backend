import { useEffect } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import { selectFeature } from "@/state/layersSlice.js";
import CircleRenderer from "../circleRenderer/CircleRenderer.jsx";
import GeoJsonRenderer from "../geoJsonRenderer/GeoJsonRenderer.jsx";

export default function FeatureRenderer({ featureRefs, itemsRef, activeToolRef }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const { items } = useLayers();
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);

  useEffect(() => {
    if (!leafletMap) return;

    const allFeatureIds = new Set();
    items.forEach((layer) => layer.features.forEach((f) => allFeatureIds.add(f.localId)));

    // Remove deleted features
    Object.keys(featureRefs.current).forEach((id) => {
      if (!allFeatureIds.has(id)) {
        try {
          leafletMap.removeLayer(featureRefs.current[id]);
        } catch (_) {}
        delete featureRefs.current[id];
      }
    });

    // Close properties popup and clear selection if the selected feature is deleted
    if (selectedFeatureId) {
      const selectedFeatureExists = items.some((layer) =>
        layer.features.some(
          (f) => f.localId === selectedFeatureId || f.backendId === selectedFeatureId
        )
      );
      if (!selectedFeatureExists) {
        dispatch(selectFeature(null));
        try {
          leafletMap.closePopup();
        } catch (_) {}
      }
    }
  }, [items, leafletMap, selectedFeatureId, featureRefs, dispatch]);

  return (
    <>
      <CircleRenderer
        featureRefs={featureRefs}
        itemsRef={itemsRef}
        activeToolRef={activeToolRef}
      />
      <GeoJsonRenderer
        featureRefs={featureRefs}
        itemsRef={itemsRef}
        activeToolRef={activeToolRef}
      />
    </>
  );
}
