// src/components/boundaryLayer/BoundaryLayer.jsx

import { useEffect, useRef, useState } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { Loader2 } from "lucide-react";
import { useBoundary } from "@/hooks/useBoundary";
import { replicateGeoJsonForInfinity } from "@/utils/InfinityMapUtils.js";

const BOUNDARY_STYLE = {
  color: "#368fe2",
  weight: 2,
  opacity: 1,
  fill: false,
};
export default function BoundaryLayer({
  type = "india",
  name = "",
  onAttribution,
}) {
  const map = useMap();
  const layerRef = useRef(null);

  const { geojson, loading, error, attribution } = useBoundary(type, name);
  const [showError, setShowError] = useState(false);

  useEffect(() => {
    if (error) {
      setShowError(true);
      const timer = setTimeout(() => {
        setShowError(false);
      }, 5000);
      return () => clearTimeout(timer);
    } else {
      setShowError(false);
    }
  }, [error]);

  useEffect(() => {
    // Remove previous boundary
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }

    if (!geojson) return;

    const replicatedGeoJson = replicateGeoJsonForInfinity(geojson);
    const layer = L.geoJSON(replicatedGeoJson, {
      style: BOUNDARY_STYLE,
    }).addTo(map);

    layerRef.current = layer;

    const bounds = L.geoJSON(geojson).getBounds();

    if (bounds.isValid()) {
      map.fitBounds(bounds, {
        padding: [40, 40],
      });
    }

    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [geojson, map]);

  useEffect(() => {
  if (attribution && onAttribution) {
    onAttribution(attribution);
  }
}, [attribution, onAttribution]);
  // Loading UI
  if (loading) {
    return (
      <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2">
        <div className="flex items-center gap-2 rounded-lg border bg-white px-4 py-2 shadow-lg">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <span className="text-sm font-medium text-gray-700">
            Loading boundary...
          </span>
        </div>
      </div>
    );
  }

  // Error UI
  if (error && showError) {
    return (
      <div className="absolute top-4 left-1/2 z-[1000] -translate-x-1/2">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 shadow-lg">
          <span className="text-sm font-medium text-red-600">
            Failed to load boundary.
          </span>
        </div>
      </div>
    );
  }

  return null;
}