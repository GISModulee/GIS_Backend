import { useEffect } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import { selectFeature, openCommentModal } from "@/state/layersSlice.js";
import { calculateRoughArea } from "@/utils/AreaUtils.js";
import { buildTooltipHTML, loadComments } from "@/utils/TooltipUtils.js";

const customPinIcon = (color, isSelected) => {
  const pinSVG = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${isSelected ? 36 : 28}" height="${isSelected ? 36 : 28}">
      <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" 
            fill="${color}" 
            stroke="${isSelected ? '#ff0000' : '#ffffff'}" 
            stroke-width="${isSelected ? 2.5 : 1.5}"
            style="filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.4));" />
    </svg>
  `;

  return L.divIcon({
    html: pinSVG,
    className: 'custom-pin-marker',
    iconSize: isSelected ? [36, 36] : [28, 28],
    iconAnchor: isSelected ? [18, 36] : [14, 28],
    popupAnchor: [0, isSelected ? -36 : -28],
  });
};

export default function FeatureRenderer({ featureRefs, itemsRef, activeToolRef }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const { items } = useLayers();
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);
  const selectedLayerId = useSelector((s) => s.layers.selectedLayerId);
  const hoveredFeatureId = useSelector((s) => s.layers.hoveredFeatureId);

  useEffect(() => {
    if (!leafletMap) return;

    const allFeatureIds = new Set();
    items.forEach((layer) => layer.features.forEach((f) => allFeatureIds.add(f.localId)));

    // Remove deleted features
    Object.keys(featureRefs.current).forEach((id) => {
      if (!allFeatureIds.has(id)) {
        try { leafletMap.removeLayer(featureRefs.current[id]); } catch (_) { }
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
        } catch (_) { }
      }
    }

    items.forEach((layer) => {
      layer.features.forEach((feature) => {
        if (!feature.geometry) return;

        const isFeatureSelected = selectedFeatureId && feature.backendId === selectedFeatureId;
        const isLayerSelected = selectedLayerId && layer.localId === selectedLayerId;
        const isSelected = isFeatureSelected || isLayerSelected;
        const isHovered = hoveredFeatureId && (feature.localId === hoveredFeatureId || feature.backendId === hoveredFeatureId);

        const shouldShow = layer.visible && feature.visible;

        const style = {
          color: isHovered ? "#111827" : (isSelected ? "#ff0000" : (feature.color || layer.color || "#2563eb")),
          weight: isHovered ? 6 : (isSelected ? 5 : 2),
          opacity: 1,
          fillOpacity: isHovered ? 0.6 : (isSelected ? 0.35 : 0.15),
        };

        // Update existing layer
        if (featureRefs.current[feature.localId]) {
          const existing = featureRefs.current[feature.localId];
          if (shouldShow && !leafletMap.hasLayer(existing)) {
            existing.addTo(leafletMap);
          } else if (!shouldShow && leafletMap.hasLayer(existing)) {
            leafletMap.removeLayer(existing);
          }
          if (existing.setStyle) {
            existing.setStyle(style);
          }
          existing.eachLayer?.((childLyr) => {
            if (childLyr.setIcon) {
              const color = isHovered ? "#111827" : (isSelected ? "#ff0000" : (feature.color || layer.color || "#2563eb"));
              childLyr.setIcon(customPinIcon(color, isSelected || isHovered));
            } else if (childLyr.setStyle) {
              childLyr.setStyle(style);
            }
          });
          return;
        }

        // Create new Leaflet layer
        const geojson = { type: "Feature", geometry: feature.geometry, properties: {} };

        const leafletLayer = L.geoJSON(geojson, {
          style,
          onEachFeature: (_f, lyr) => {
            // Click to select and show properties
            lyr.on("click", function (e) {
              L.DomEvent.stopPropagation(e);
              console.log("[FeatureRenderer] Map feature clicked:", feature);

              const latestItems = itemsRef.current;
              const currentLayer = latestItems.find((l) => l.localId === feature.layerLocalId);
              const currentFeature = currentLayer?.features.find((f) => f.localId === feature.localId) || feature;

              if (activeToolRef.current === "comment") {
                if (currentFeature.backendId) {
                  dispatch(openCommentModal(currentFeature.backendId));
                } else {
                  alert("Save this feature first before adding a comment.");
                }
                return;
              }

              const selectionId = currentFeature.backendId || currentFeature.localId;
              dispatch(selectFeature(selectionId));

              // Show properties popup on click
              try {
                const area = calculateRoughArea(currentFeature);
                const containerPoint = leafletMap.latLngToContainerPoint(e.latlng);
                const mapSize = leafletMap.getSize();

                let offsetX = 0;
                let offsetY = -10;
                let isNearTop = false;

                // Adjust vertical position if clicked near the top boundary
                if (containerPoint.y < 265) {
                  offsetY = 240; // Shift downward below the point
                  isNearTop = true;
                }

                // Adjust horizontal position if clicked near left or right boundaries
                const minEdgeMargin = 120; // Half-width of popup + safe margin
                if (containerPoint.x < minEdgeMargin) {
                  offsetX = minEdgeMargin - containerPoint.x; // Shift right
                } else if (containerPoint.x > mapSize.x - minEdgeMargin) {
                  offsetX = -(minEdgeMargin - (mapSize.x - containerPoint.x)); // Shift left
                }

                const offset = [offsetX, offsetY];
                const className = isNearTop
                  ? "feature-tooltip-popup feature-tooltip-popup-top"
                  : "feature-tooltip-popup";

                L.popup({
                  offset: offset,
                  className: className,
                  autoPan: true,
                  autoPanPadding: [30, 30],
                })
                .setLatLng(e.latlng)
                .setContent(buildTooltipHTML(currentFeature, currentLayer || layer, area))
                .openOn(leafletMap);
                setTimeout(() => loadComments(currentFeature), 50);
              } catch (_) { }
            });
          },

          pointToLayer: (_f, latlng) => {
            const radius = feature.geometry?.radius;
            if (radius != null) return L.circle(latlng, { radius, ...style });
            const color = isHovered ? "#111827" : (isSelected ? "#ff0000" : (feature.color || layer.color || "#2563eb"));
            return L.marker(latlng, {
              icon: customPinIcon(color, isSelected || isHovered)
            });
          },
        });

        if (shouldShow) leafletLayer.addTo(leafletMap);
        featureRefs.current[feature.localId] = leafletLayer;
      });
    });

  }, [items, leafletMap, selectedFeatureId, selectedLayerId, hoveredFeatureId, featureRefs, itemsRef, activeToolRef, dispatch]);

  return null;
}
