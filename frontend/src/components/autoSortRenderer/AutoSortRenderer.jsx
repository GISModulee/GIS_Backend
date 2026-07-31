import { useEffect } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import { calculateRoughArea } from "@/utils/AreaUtils.js";

export default function AutoSortRenderer({ featureRefs }) {
  const leafletMap = useLeafletMap();
  const { items } = useLayers();

  useEffect(() => {
    if (!leafletMap) return;

    const layersToSort = [];
    items.forEach((layer) => {
      layer.features.forEach((feature) => {
        if (!feature.geometry) return;
        const shouldShow = layer.visible && feature.visible;
        if (shouldShow && featureRefs.current[feature.localId]) {
          layersToSort.push({
            leafletLayer: featureRefs.current[feature.localId],
            area: calculateRoughArea(feature),
          });
        }
      });
    });

    // Sort descending (largest area first)
    layersToSort.sort((a, b) => b.area - a.area);

    // Bring to front in order, so smallest ends up on very top
    layersToSort.forEach((item) => {
      if (item.leafletLayer && typeof item.leafletLayer.bringToFront === 'function') {
        item.leafletLayer.bringToFront();
      }
    });
  }, [items, leafletMap, featureRefs]);

  return null;
}
