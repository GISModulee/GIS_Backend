import { useEffect, useMemo } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import { selectFeature, openCommentModal } from "@/state/layersSlice.js";
import { calculateRoughArea } from "@/utils/AreaUtils.js";
import { buildTooltipHTML, loadComments } from "@/utils/TooltipUtils.js";

export default function CircleRenderer({ featureRefs, itemsRef, activeToolRef }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const { items } = useLayers();
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);
  const selectedLayerId = useSelector((s) => s.layers.selectedLayerId);
  const hoveredFeatureId = useSelector((s) => s.layers.hoveredFeatureId);

  // Initialize a single canvas renderer to group draw calls on the GPU
  const canvasRenderer = useMemo(() => L.canvas({ padding: 0.5 }), []);

  useEffect(() => {
    if (!leafletMap) return;

    items.forEach((layer) => {
      layer.features.forEach((feature) => {
        if (!feature.geometry) return;

        const isCircleType = feature.geometry_type === "Circle" || feature.type === "circle";
        if (!isCircleType) return;

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
          return;
        }

        // Resolve center and radius
        let centerLatLng = null;
        if (feature.center) {
          centerLatLng = [feature.center.lat, feature.center.lng];
        } else if (feature.properties?.center) {
          centerLatLng = [feature.properties.center.lat, feature.properties.center.lng];
        } else if (feature.geometry?.type === "Point" && Array.isArray(feature.geometry.coordinates)) {
          centerLatLng = [feature.geometry.coordinates[1], feature.geometry.coordinates[0]];
        }
        const radius = feature.radius || feature.properties?.radius || feature.geometry?.radius;

        // if (centerLatLng && radius != null) {
        //   const leafletLayer = L.circle(centerLatLng, {
        //     radius: radius,
        //     ...style,
        //     noWrap: true
        //   });
        if (centerLatLng && radius != null) {
          // 1. Calculate the latitude distortion factor (cos of latitude)
          const rad = (centerLatLng.lat * Math.PI) / 180;
          const projectionFactor = Math.cos(rad);

          // 2. Pass the corrected options to lock the rendering ratio
          const leafletLayer = L.circle(centerLatLng, {
            radius: radius,
            renderer: canvasRenderer,
            ...style,
            noWrap: true
          });

          leafletLayer.on("click", function (e) {
            L.DomEvent.stopPropagation(e);
            console.log("[CircleRenderer] Map circle feature clicked:", feature);

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

              if (containerPoint.y < 265) {
                offsetY = 240;
                isNearTop = true;
              }

              const minEdgeMargin = 120;
              if (containerPoint.x < minEdgeMargin) {
                offsetX = minEdgeMargin - containerPoint.x;
              } else if (containerPoint.x > mapSize.x - minEdgeMargin) {
                offsetX = -(minEdgeMargin - (mapSize.x - containerPoint.x));
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

          if (shouldShow) leafletLayer.addTo(leafletMap);
          featureRefs.current[feature.localId] = leafletLayer;
        }
      });
    });
  }, [items, leafletMap, selectedFeatureId, selectedLayerId, hoveredFeatureId, featureRefs, itemsRef, activeToolRef, dispatch]);

  return null;
}
