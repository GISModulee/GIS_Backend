import axiosInstance from "@/api/axiosInstance.js";
import { API_ENDPOINTS } from "@/config/apiConfig.js";

function parseNdjsonToGeojson(ndjsonText) {
  if (!ndjsonText || typeof ndjsonText !== "string") {
    return ndjsonText;
  }

  try {
    const trimmed = ndjsonText.trim();
    if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
      const parsed = JSON.parse(trimmed);
      if (parsed.boundary || parsed.type === "Feature" || parsed.type === "FeatureCollection") {
        return parsed;
      }
    }
  } catch (e) {
    // Not a single JSON object, proceed to parse as NDJSON
  }

  const lines = ndjsonText.split("\n").filter(line => line.trim());
  if (lines.length === 0) return null;

  let meta = null;
  const rings = [];

  for (const line of lines) {
    try {
      const parsed = JSON.parse(line);
      if (parsed.type === "meta") {
        meta = parsed;
      } else if (parsed.type === "ring") {
        rings.push(parsed.coordinates);
      }
    } catch (e) {
      console.error("[parseNdjsonToGeojson] Error parsing line:", e);
    }
  }

  if (!meta) {
    return null;
  }

  const geometryType = meta.geometry_type || "MultiPolygon";
  let coordinates = [];

  if (geometryType === "MultiPolygon") {
    coordinates = rings.map(ring => [ring]);
  } else {
    coordinates = rings;
  }

  return {
    boundary: {
      type: "Feature",
      properties: {
        source: meta.source || "",
      },
      geometry: {
        type: geometryType,
        coordinates: coordinates,
      }
    },
    attribution: meta.attribution || null
  };
}

const boundaryService = {
  async getIndiaBoundary() {
    const { data } = await axiosInstance.get(API_ENDPOINTS.BOUNDARIES.INDIA);
    return parseNdjsonToGeojson(data);
  },

  async getStateBoundary(stateName) {
    const { data } = await axiosInstance.get(API_ENDPOINTS.BOUNDARIES.STATE(stateName));
    return parseNdjsonToGeojson(data);
  },

  async getDistrictBoundary(districtName) {
    const { data } = await axiosInstance.get(API_ENDPOINTS.BOUNDARIES.DISTRICT(districtName));
    return parseNdjsonToGeojson(data);
  },
};

export default boundaryService;
