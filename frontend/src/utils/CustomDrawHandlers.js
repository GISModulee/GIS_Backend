import L from "leaflet";
import * as turf from "@turf/turf";

export function getDrawType(layerType) {
  const map = {
    polygon: "polygon",
    polyline: "polyline",
    rectangle: "rectangle",
    marker: "point",
    circle: "circle",
  };
  return map[layerType] || "polygon";
}

export function extractGeometry(layer, layerType) {
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
export const SHAPE_COLORS = {
  polygon: "#000000ff",  // blue
  polyline: "#16a34a",  // green
  rectangle: "#ea3395ff",  // purple
  point: "#8b5cf6",  // purple (for custom points)
  circle: "#ea580c",  // orange
  measure: "#000000",  // black
};

// Round icon for vertex points instead of default square
export const roundIcon = (color) =>
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

export class FourPointRectangle extends L.Draw.Polygon {
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

export class TwoPointPolyline extends L.Draw.Polyline {
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

export class CircleWithRadiusLine extends L.Draw.Circle {
  _onMouseDown(e) {
    if (!this._isDrawing) {
      this._isDrawing = true;
      this._startLatLng = e.latlng;
      L.DomEvent.preventDefault(e.originalEvent);
    } else {
      if (this._shape) {
        this._fireCreatedEvent();
      }
      this.disable();
      if (this.options.repeatMode) {
        this.enable();
      }
    }
  }

  _onMouseUp() {
    // No-op: we handle finishing the shape on the second mousedown/click instead of mouseup
  }

  _onMouseMove(e) {
    super._onMouseMove(e);
    if (this._enabled && this._startLatLng) {
      const currentLatLng = e.latlng;
      const color = this.options.geodesicStyle?.color || this.options.shapeOptions?.color || '#2563eb';
      const radius = this._startLatLng.distanceTo(currentLatLng);

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

      // 3. Draw/update geodesic circle polygon
      const center = [this._startLatLng.lng, this._startLatLng.lat];
      const turfCircle = turf.circle(center, radius, { units: 'meters', steps: 64 });
      const latlngs = turfCircle.geometry.coordinates[0].map(coord => [coord[1], coord[0]]);

      if (!this._geodesicShape) {
        this._geodesicShape = L.polygon(latlngs, {
          color: color,
          weight: this.options.geodesicStyle?.weight || 2,
          fillColor: color,
          fillOpacity: this.options.geodesicStyle?.fillOpacity || 0.15,
          opacity: this.options.geodesicStyle?.opacity || 1,
          interactive: false
        }).addTo(this._map);
      } else {
        this._geodesicShape.setLatLngs(latlngs);
      }
    }
  }

  _drawShape(latlng) {
    super._drawShape(latlng);
    if (this._shape) {
      this._shape.setStyle({
        opacity: 0,
        fillOpacity: 0,
        interactive: false
      });
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
      if (this._geodesicShape) {
        this._map.removeLayer(this._geodesicShape);
        this._geodesicShape = null;
      }
    }
  }
}
