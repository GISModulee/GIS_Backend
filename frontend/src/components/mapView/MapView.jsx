// src/components/mapView/MapView.jsx
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector } from "react-redux";
import { useMap } from "@/hooks/useMap.js";
import { MAP_PROVIDERS, DEFAULT_BASEMAP } from "@/config/apiConfig.js";
import BoundaryLayer from "@/components/boundaryLayer/BoundaryLayer.jsx";
import MapController from "@/components/mapController/MapController.jsx";
import DrawingManager from "@/components/drawingManager/DrawingManager.jsx";
import LayerRenderer from "../layerRenderer/LayerRenderer.jsx";
import CursorWebSocket from "../cursorWebSocket/CursorWebSocket.jsx";
import { useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import L from "leaflet";

function TileLayerSwitcher() {
  const { basemapId } = useMap();
  const provider = MAP_PROVIDERS[basemapId] || MAP_PROVIDERS[DEFAULT_BASEMAP];
  return (
    <TileLayer
      key={basemapId}
      url={provider.url}
      attribution=""
      subdomains={provider.subdomains || "abc"}
      maxZoom={18}
      noWrap={true}
    />
  );
}

function AttributionInjector({ attribution }) {
  const map = useLeafletMap();
  useEffect(() => {
    if (attribution) {
      const control = L.control.attribution({ prefix: attribution.prefix })
        .addTo(map)
        .addAttribution(attribution.html);

      return () => {
        control.remove();
      };
    }
  }, [attribution, map]);
  return null;
}

const worldBounds = L.latLngBounds(
  [-85.05112878, -180],
  [85.05112878, 180]
);

function MapResizer({ sidebarOpen }) {
  const map = useLeafletMap();

  useEffect(() => {
    if (!map) return;

    const updateMapLayout = () => {
      window.requestAnimationFrame(() => {
        try {
          map.invalidateSize({ pan: false });
          const minimumCoverZoom = map.getBoundsZoom(worldBounds, true);
          map.setMinZoom(minimumCoverZoom);
          if (map.getZoom() < minimumCoverZoom) {
            map.setZoom(minimumCoverZoom);
          }
          map.panInsideBounds(worldBounds, { animate: false });
        } catch (e) {
          console.warn("Error invalidating map size:", e);
        }
      });
    };

    // 1. Initial trigger
    updateMapLayout();

    // 2. ResizeObserver for map container
    const container = map.getContainer();
    let resizeObserver = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        updateMapLayout();
      });
      resizeObserver.observe(container);
    }

    // 3. transitionend event listener on parent wrapper
    const transitionContainer = container.parentElement;
    const handleTransitionEnd = (e) => {
      if (e.propertyName === "left" || e.propertyName === "width" || e.propertyName === "transform") {
        updateMapLayout();
      }
    };

    if (transitionContainer) {
      transitionContainer.addEventListener("transitionend", handleTransitionEnd);
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (transitionContainer) {
        transitionContainer.removeEventListener("transitionend", handleTransitionEnd);
      }
    };
  }, [map, sidebarOpen]);

  return null;
}

const indiaBounds = [
  [6.75, 68.18],
  [37.08, 97.42],
];

export default function MapView({ sidebarOpen }) {
  const { caseId } = useParams();
  const resultLayers = useSelector((s) => s.layers.resultLayers) || [];
  const [attribution, setAttribution] = useState(null);

  return (
    <div className="w-full h-full">
      <MapContainer
        preferCanvas={true}
        center={[22.9, 78.9]}
        zoom={5}
        zoomControl={false}
        attributionControl={false}
        maxBounds={worldBounds}
        maxBoundsViscosity={1.0}
        worldCopyJump={false}
        minZoom={2}
        className="w-full h-full"
        style={{ height: "100%", width: "100%" }}
      >
        <MapResizer sidebarOpen={sidebarOpen} />
        <TileLayerSwitcher />
        <MapController />
        <BoundaryLayer type="india" onAttribution={setAttribution} />
        <AttributionInjector attribution={attribution} />
        <DrawingManager />
        <LayerRenderer />
        <CursorWebSocket caseId={caseId} />

        {/* Render computed results layers from Turf */}
        {resultLayers
          .filter((r) => r.visible)
          .map((r) => (
            <GeoJSON
              key={r.id}
              data={r.geojson}
              style={{
                color: r.color,
                fillColor: r.color,
                fillOpacity: 0.25,
                weight: 2.5,
                dashArray: "6 4", // dashed = "this is a computed result"
              }}
            />
          ))}
      </MapContainer>
    </div>
  );
}