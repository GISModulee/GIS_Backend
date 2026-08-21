// src/components/drawingManager/DrawingManager.jsx
import { useEffect, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";
import { useMap } from "@/hooks/useMap.js";
import { useLayers } from "@/hooks/useLayers.js";
import {
  getDrawType,
  extractGeometry,
  SHAPE_COLORS,
  roundIcon,
  TwoPointPolyline,
  CircleWithRadiusLine,
} from "@/utils/CustomDrawHandlers.js";

export default function DrawingManager({ onColorChange }) {
  const leafletMap = useLeafletMap();
  const { activeTool, changeActiveTool } = useMap();
  const { holdDrawnShape } = useLayers();

  const drawnLayersRef = useRef(null);
  const activeHandlerRef = useRef(null);
  const activeToolRef = useRef(activeTool);

  useEffect(() => {
    activeToolRef.current = activeTool;
  }, [activeTool]);

  useEffect(() => {
    if (!leafletMap) return;

    if (!drawnLayersRef.current) {
      drawnLayersRef.current = new L.FeatureGroup().addTo(leafletMap);
    }

    const handleCreated = (e) => {
      const layer = e.layer;

      if (activeToolRef.current === "measure") {
        // Just discard the measurement line instead of keeping it
        changeActiveTool("select");
        return;
      }

      const layerType = e.layerType;
      const type = layer._rectangleMode ? "rectangle" : getDrawType(layerType);
      const geometry = extractGeometry(layer, layerType);
      const color = SHAPE_COLORS[type] || "#2563eb";

      // Remove the temporary layer created by leaflet-draw to prevent duplication
      if (layer && typeof layer.remove === "function") {
        layer.remove();
      } else if (layer) {
        leafletMap.removeLayer(layer);
      }

      holdDrawnShape(geometry, type, color);  // ← pass color
      changeActiveTool("select");
    };

    leafletMap.on(L.Draw.Event.CREATED, handleCreated);

    return () => {
      leafletMap.off(L.Draw.Event.CREATED, handleCreated);
    };
  }, [leafletMap]);

  useEffect(() => {
    if (!leafletMap) return;

    if (activeHandlerRef.current) {
      activeHandlerRef.current.disable();
      activeHandlerRef.current = null;
    }

    if (!L.Draw) return;

    const color = SHAPE_COLORS[activeTool] || "#2563eb";

    const shapeOpts = {
      shapeOptions: {
        color,
        weight: 2,
        fillOpacity: 0.15,
        opacity: 1,
      },
      // Round circle markers for vertices instead of default squares
      icon: roundIcon(color),
      touchIcon: roundIcon(color),
    };

    const handlers = {
      polygon: () => new L.Draw.Polygon(leafletMap, shapeOpts),
      polyline: () =>
        new TwoPointPolyline(leafletMap, {
          shapeOptions: {
            color,
            weight: 2,
            opacity: 1,
          },
          icon: roundIcon(color),
          touchIcon: roundIcon(color),
        }),
      measure: () => new TwoPointPolyline(leafletMap, shapeOpts),
      rectangle: () => new L.Draw.Rectangle(leafletMap, {
        ...shapeOpts,
        showArea: false,  // ← disables the area tooltip that has the bug
      }),
      point: () => new L.Draw.Marker(leafletMap),
      circle: () => {
        const circleOpts = {
          ...shapeOpts,
          shapeOptions: {
            ...shapeOpts.shapeOptions,
            opacity: 0,
            fillOpacity: 0,
          },
          geodesicStyle: shapeOpts.shapeOptions
        };
        return new CircleWithRadiusLine(leafletMap, circleOpts);
      },
    };

    if (handlers[activeTool]) {
      activeHandlerRef.current = handlers[activeTool]();
      activeHandlerRef.current.enable();
    }
  }, [activeTool, leafletMap]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Enter" && activeTool === "polygon" && activeHandlerRef.current) {
        if (typeof activeHandlerRef.current.completeShape === "function") {
          activeHandlerRef.current.completeShape();
        } else if (typeof activeHandlerRef.current._finishShape === "function") {
          activeHandlerRef.current._finishShape();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [activeTool]);

  DrawingManager.clearTempLayer = () => { };

  return null;
}