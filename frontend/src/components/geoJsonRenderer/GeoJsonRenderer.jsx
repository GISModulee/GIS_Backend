import { useEffect, useMemo, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import { selectFeature, openCommentModal, setHoveredFeatureId } from "@/state/layersSlice.js";
import { calculateRoughArea } from "@/utils/AreaUtils.js";
import { buildTooltipHTML } from "@/utils/TooltipUtils.js";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

export default function GeoJsonRenderer({ featureRefs, itemsRef, activeToolRef }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const { items } = useLayers();
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);
  const selectedLayerId = useSelector((s) => s.layers.selectedLayerId);
  const hoveredFeatureId = useSelector((s) => s.layers.hoveredFeatureId);

  // Initialize a single canvas renderer to group draw calls on the GPU

  const clusterGroupsRef = useRef({});

  useEffect(() => {
    if (!leafletMap) return;

    // Clean up deleted layers/cluster groups
    const currentLayerIds = new Set(items.map(l => String(l.localId)));
    Object.keys(clusterGroupsRef.current).forEach((layerId) => {
      if (!currentLayerIds.has(String(layerId))) {
        const group = clusterGroupsRef.current[layerId];
        if (leafletMap.hasLayer(group)) {
          leafletMap.removeLayer(group);
        }
        delete clusterGroupsRef.current[layerId];
      }
    });

    // Cleanup featureRefs that are no longer in items
    const currentFeatureLocalIds = new Set();
    items.forEach((layer) => {
      layer.features.forEach((feature) => {
        currentFeatureLocalIds.add(feature.localId);
      });
    });

    Object.keys(featureRefs.current).forEach((localId) => {
      if (!currentFeatureLocalIds.has(localId)) {
        const existing = featureRefs.current[localId];
        Object.values(clusterGroupsRef.current).forEach((group) => {
          if (existing.eachLayer) {
            existing.eachLayer((layer) => {
              if (group.hasLayer(layer)) {
                group.removeLayer(layer);
              }
            });
          } else {
            if (group.hasLayer(existing)) {
              group.removeLayer(existing);
            }
          }
        });
        if (leafletMap.hasLayer(existing)) {
          leafletMap.removeLayer(existing);
        }
        delete featureRefs.current[localId];
      }
    });

    // Process each layer and feature
    items.forEach((layer) => {
      // Ensure cluster group exists for points in this layer
      if (!clusterGroupsRef.current[layer.localId]) {
        clusterGroupsRef.current[layer.localId] = L.markerClusterGroup({
          maxClusterRadius: 60,
          showCoverageOnHover: false,
          iconCreateFunction: (cluster) => {
            const childCount = cluster.getChildCount();
            let sizeClass = 'marker-cluster-small';
            if (childCount >= 100) sizeClass = 'marker-cluster-large';
            else if (childCount >= 10) sizeClass = 'marker-cluster-medium';
            return L.divIcon({
              html: `<div><span>${childCount}</span></div>`,
              className: `marker-cluster marker-cluster-custom ${sizeClass}`,
              iconSize: L.point(40, 40)
            });
          }
        });
      }

      const clusterGroup = clusterGroupsRef.current[layer.localId];
      if (layer.visible) {
        if (!leafletMap.hasLayer(clusterGroup)) {
          leafletMap.addLayer(clusterGroup);
        }
      } else {
        if (leafletMap.hasLayer(clusterGroup)) {
          leafletMap.removeLayer(clusterGroup);
        }
      }

      layer.features.forEach((feature) => {
        if (!feature.geometry) return;
        const isCircleType = (feature.geometry_type === "Circle" || feature.type === "circle") && feature.geometry.type === "Point";
        if (isCircleType) return;

        const isFeatureSelected = selectedFeatureId && (
          feature.backendId === selectedFeatureId ||
          feature.localId === selectedFeatureId ||
          (feature.backendId && Number(feature.backendId) === Number(selectedFeatureId))
        );
        const isLayerSelected = selectedLayerId && layer.localId === selectedLayerId;
        const isSelected = isFeatureSelected || isLayerSelected;
        const isHovered = hoveredFeatureId && (feature.localId === hoveredFeatureId || feature.backendId === hoveredFeatureId);

        const shouldShow = layer.visible && feature.visible;

        const isPoint = feature.geometry.type === "Point" || feature.geometry.type === "MultiPoint";
        const colorVal = feature.color || layer.color || "#dc2626";
        const style = {
          color: isSelected ? "#ff0000" : (isPoint ? "#ffffff" : colorVal),
          weight: isPoint ? (isSelected || isHovered ? 2 : 1) : (isHovered ? 6 : (isSelected ? 5 : 2)),
          opacity: 1,
          fillColor: isSelected ? "#ff0000" : colorVal,
          fillOpacity: isPoint ? (isHovered ? 0.95 : (isSelected ? 0.85 : 0.8)) : (isHovered ? 0.6 : (isSelected ? 0.35 : 0.15)),
          ...(isPoint ? { radius: 6 } : {})
        };

        if (isPoint) {
          // Point layer optimization (CircleMarker + Cluster)
          if (featureRefs.current[feature.localId]) {
            const existing = featureRefs.current[feature.localId];
            if (existing.eachLayer) {
              if (shouldShow) {
                existing.eachLayer((layer) => {
                  if (!clusterGroup.hasLayer(layer)) {
                    clusterGroup.addLayer(layer);
                  }
                });
              } else {
                existing.eachLayer((layer) => {
                  if (clusterGroup.hasLayer(layer)) {
                    clusterGroup.removeLayer(layer);
                  }
                });
              }
              existing.eachLayer((layer) => {
                if (layer.setStyle) {
                  layer.setStyle(style);
                }
              });
            } else {
              if (shouldShow) {
                if (!clusterGroup.hasLayer(existing)) {
                  clusterGroup.addLayer(existing);
                }
              } else {
                if (clusterGroup.hasLayer(existing)) {
                  clusterGroup.removeLayer(existing);
                }
              }
              if (existing.setStyle) {
                existing.setStyle(style);
              }
            }
            return;
          }

          const geojson = { type: "Feature", geometry: feature.geometry, properties: {} };
          const leafletLayer = L.geoJSON(geojson, {
            style,
            onEachFeature: (_f, lyr) => {
              lyr.on("click", function (e) {
                L.DomEvent.stopPropagation(e);
                console.log("[GeoJsonRenderer] Map point clicked:", feature);

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
                } catch (_) { }
              });
            },
            pointToLayer: (_f, latlng) => {
              const radius = feature.geometry?.radius;
              if (radius != null && feature.geometry_type !== "Circle") return L.circle(latlng, { radius, ...style, interactive: true });
              return L.circleMarker(latlng, {
                ...style,
                interactive: true
              });
            }
          });

          if (shouldShow) {
            leafletLayer.eachLayer((layer) => {
              clusterGroup.addLayer(layer);
            });
          }
          featureRefs.current[feature.localId] = leafletLayer;

        } else {
          // Polygon/Line layer (No Cluster)
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

          const geojson = { type: "Feature", geometry: feature.geometry, properties: {} };
          const leafletLayer = L.geoJSON(geojson, {
            style,
            onEachFeature: (_f, lyr) => {
              lyr.on("click", function (e) {
                L.DomEvent.stopPropagation(e);
                console.log("[GeoJsonRenderer] Map shape clicked:", feature);

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
                } catch (_) { }
              });
            }
          });

          if (shouldShow) leafletLayer.addTo(leafletMap);
          featureRefs.current[feature.localId] = leafletLayer;
        }
      });
    });

    return () => {
      Object.values(clusterGroupsRef.current).forEach((group) => {
        if (leafletMap.hasLayer(group)) {
          leafletMap.removeLayer(group);
        }
      });
    };
  }, [items, leafletMap, selectedFeatureId, selectedLayerId, hoveredFeatureId, featureRefs, itemsRef, activeToolRef, dispatch]);

  return null;
}
