import { useEffect } from "react";
import { useMap as useLeafletMap, useMapEvents } from "react-leaflet";
import { useMap } from "@/hooks/useMap.js";
import { useDispatch } from "react-redux";
import { setViewport } from "@/state/mapSlice.js";
import { selectFeature } from "@/state/layersSlice.js";

export default function MapController() {
  const leafletMap = useLeafletMap();
  const { registerMapInstance } = useMap();
  const dispatch = useDispatch();

  useMapEvents({
    click: () => {
      // Deselect when clicking empty space on the map
      dispatch(selectFeature(null));
    },
    zoomend: (e) => {
      dispatch(setViewport({ zoom: e.target.getZoom() }));
    },
    moveend: (e) => {
      const center = e.target.getCenter();
      dispatch(setViewport({ center: [center.lat, center.lng] }));
    },
  });

  useEffect(() => {
    if (leafletMap) {
      registerMapInstance(leafletMap);
    }
  }, [leafletMap, registerMapInstance]);

  return null;
}