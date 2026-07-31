import React, { useEffect, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import { useMap } from "@/hooks/useMap.js";
import FeatureRenderer from "../featureRenderer/FeatureRenderer.jsx";
import CommentRenderer from "../commentRenderer/CommentRenderer.jsx";
import AutoSortRenderer from "../autoSortRenderer/AutoSortRenderer.jsx";

export default function LayerRenderer() {
  const leafletMap = useLeafletMap();
  const { items } = useLayers();
  const { activeTool } = useMap();
  const backendGeoJson = useSelector((s) => s.layers.backendGeoJson);

  const featureRefs = useRef({});
  const commentRefs = useRef({});
  const backendLayerRef = useRef(null);

  const activeToolRef = useRef(activeTool);
  useEffect(() => {
    activeToolRef.current = activeTool;
  }, [activeTool]);

  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  // ── Cursor for comment mode ─────────────────────────────
  useEffect(() => {
    if (!leafletMap) return;
    leafletMap.getContainer().style.cursor =
      activeTool === "comment" ? "crosshair" : "";
  }, [activeTool, leafletMap]);

  // ── Backend GeoJSON layer (GeoCLIP) ── from doc 18 ──────
  useEffect(() => {
    if (!leafletMap || !backendGeoJson) return;
    if (backendLayerRef.current) {
      try { leafletMap.removeLayer(backendLayerRef.current); } catch (_) { }
    }

    backendLayerRef.current = L.geoJSON(backendGeoJson, {
      pointToLayer: (f, latlng) =>
        L.circleMarker(latlng, {
          radius: 8,
          color: f.properties?.color || "#dc2626",
        }),
    }).addTo(leafletMap);

    const bounds = backendLayerRef.current.getBounds();
    if (bounds.isValid()) leafletMap.fitBounds(bounds, { padding: [40, 40] });
  }, [backendGeoJson, leafletMap]);

  // ── Static helpers ──────────────────────────────────────
  LayerRenderer.flyToFeature = (identifier, map) => {
    let lyr = featureRefs.current[identifier];
    if (!lyr) {
      const foundFeature = itemsRef.current
        .flatMap((layer) => layer.features)
        .find((f) => f.backendId === identifier || f.localId === identifier);
      if (foundFeature) {
        lyr = featureRefs.current[foundFeature.localId];
      }
    }
    if (!lyr || !map) return;
    try {
      const bounds = lyr.getBounds?.();
      if (bounds?.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
      } else {
        let foundLatLng = null;
        lyr.eachLayer?.((l) => {
          if (l.getLatLng) {
            foundLatLng = l.getLatLng();
          } else if (l.getBounds) {
            const b = l.getBounds();
            if (b.isValid()) foundLatLng = b.getCenter();
          }
        });
        if (foundLatLng) {
          map.setView(foundLatLng, 16);
        }
      }
    } catch (_) { }
  };

  LayerRenderer.flyToLayer = (layerLocalId, items, map) => {
    if (!map) return;
    const layer = items.find((l) => l.localId === layerLocalId);
    if (!layer) return;
    const bounds = L.latLngBounds([]);
    layer.features.forEach((f) => {
      const lyr = featureRefs.current[f.localId];
      if (lyr?.getBounds) try { bounds.extend(lyr.getBounds()); } catch (_) { }
    });
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
  };

  return (
    <>
      <FeatureRenderer 
        featureRefs={featureRefs} 
        itemsRef={itemsRef} 
        activeToolRef={activeToolRef} 
      />
      <CommentRenderer 
        commentRefs={commentRefs} 
        itemsRef={itemsRef} 
      />
      <AutoSortRenderer 
        featureRefs={featureRefs} 
      />
    </>
  );
}