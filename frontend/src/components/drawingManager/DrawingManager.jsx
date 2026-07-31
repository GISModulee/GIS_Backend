// src/components/drawingManager/DrawingManager.jsx
import { useEffect, useRef, useState } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-draw/dist/leaflet.draw.css";
import "leaflet-draw";
import { useMap } from "@/hooks/useMap.js";
import { useLayers } from "@/hooks/useLayers.js";

function getDrawType(layerType) {
  const map = {
    polygon: "polygon",
    polyline: "polyline",
    rectangle: "rectangle",
    marker: "point",
    circle: "circle",
  };
  return map[layerType] || "polygon";
}

function extractGeometry(layer, layerType) {
  if (layerType === "circle") {
    const latlng = layer.getLatLng();
    return {
      type: "Point",
      coordinates: [latlng.lng, latlng.lat],
      center: {
        lat: latlng.lat,
        lng: latlng.lng,
      },
      radius: layer.getRadius(),
    };
  }
  return layer.toGeoJSON().geometry;
}

// Shape colors — each draw tool gets a distinct color
const SHAPE_COLORS = {
  polygon: "#000000ff",  // blue
  polyline: "#16a34a",  // green
  rectangle: "#ea3395ff",  // purple
  point: "#8b5cf6",  // purple (for custom points)
  circle: "#ea580c",  // orange
  measure: "#000000",  // black
};

// Round icon for vertex points instead of default square
const roundIcon = (color) =>
  L.divIcon({
    className: "",
    html: `<div style="
      width: 10px; height: 10px;
      border-radius: 50%;
      background: ${color};
      border: 2px solid white;
      box-shadow: 0 0 3px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });

class FourPointRectangle extends L.Draw.Polygon {
  constructor(map, options) {
    super(map, { ...options, showArea: false, allowIntersection: false });
    this._rectangleMode = true;
  }
  addVertex(latlng) {
    super.addVertex(latlng);
    if (this._markers && this._markers.length === 4) {
      if (typeof this.completeShape === "function") {
        this.completeShape();
      } else if (typeof this._finishShape === "function") {
        this._finishShape();
      }
    }
  }
}

class TwoPointPolyline extends L.Draw.Polyline {
  addVertex(latlng) {
    super.addVertex(latlng);
    if (this._markers && this._markers.length === 2) {
      if (typeof this.completeShape === "function") {
        this.completeShape();
      } else if (typeof this._finishShape === "function") {
        this._finishShape();
      }
    }
  }
}

class CircleWithRadiusLine extends L.Draw.Circle {
  _onMouseMove(e) {
    super._onMouseMove(e);
    if (this._enabled && this._startLatLng) {
      const currentLatLng = e.latlng;
      const color = this.options.shapeOptions?.color || '#2563eb';

      // 1. Draw/update center point
      if (!this._centerMarker) {
        this._centerMarker = L.circleMarker(this._startLatLng, {
          radius: 4,
          color: color,
          fillColor: '#ffffff',
          fillOpacity: 1,
          weight: 2,
          interactive: false
        }).addTo(this._map);
      }

      // 2. Draw/update radius line
      if (!this._radiusLine) {
        this._radiusLine = L.polyline([this._startLatLng, currentLatLng], {
          color: color,
          weight: 2,
          dashArray: '5, 5',
          interactive: false
        }).addTo(this._map);
      } else {
        this._radiusLine.setLatLngs([this._startLatLng, currentLatLng]);
      }
    }
  }

  _clearLayer() {
    super._clearLayer();
    this._cleanUpCustomLayers();
  }

  disable() {
    super.disable();
    this._cleanUpCustomLayers();
  }

  _cleanUpCustomLayers() {
    if (this._map) {
      if (this._radiusLine) {
        this._map.removeLayer(this._radiusLine);
        this._radiusLine = null;
      }
      if (this._centerMarker) {
        this._map.removeLayer(this._centerMarker);
        this._centerMarker = null;
      }
    }
  }
}

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

  // Current draw color based on active tool
  const currentColor = SHAPE_COLORS[activeTool] || "#2563eb";

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
      circle: () => new CircleWithRadiusLine(leafletMap, shapeOpts),
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