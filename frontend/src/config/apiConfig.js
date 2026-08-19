// src/config/apiConfig.js

// ── Two separate backends ─────────────────────────────────
export const API_URLS = {
  GEO: "http://192.168.6.63:8082/api",                          // boundaries, tiles
  // LAYERS: "https://crabbing-nickname-easeful.ngrok-free.dev",    // cases, layers, features
  LAYERS: "http://192.168.8.65:8000",    // cases, layers, features
  // LAYERS: "http://192.168.8.168:8000",
};


// ── Fixed active case ─────────────────────────────────────
export const ACTIVE_CASE_ID = 47;

// ── Shared config ─────────────────────────────────────────
export const API_CONFIG = {
  BASE_URL: API_URLS.GEO,  // kept for backwards compat
  HEADERS: {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true",
  },
  // TIMEOUT: 15000,
};


// ── App Config ────────────────────────────────────────────
// Flip to true when backend is ready — no other changes needed anywhere
export const BACKEND_ENABLED = true;

// ── Map Providers ─────────────────────────────────────────
export const MAP_PROVIDERS = {
  custom: {
    id: 'custom',
    label: 'Custom Tiles',
    url: `${API_URLS.GEO}/tiles/{z}/{x}/{y}.png`,
    attribution: '&copy; Self-Hosted OSM',
    subdomains: '',
    maxZoom: 19,
    color: '#2563eb',
  },
  esriSatellite: {
    id: 'esriSatellite',
    label: 'ESRI Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, USGS, NASA',
    subdomains: '',
    maxZoom: 19,
    color: '#166534',
  },
  cartoLight: {
    id: 'cartoLight',
    label: 'Carto Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CartoDB',
    subdomains: 'abcd',
    maxZoom: 19,
    color: '#e2e8f0',
  },
  dark: {
    id: 'dark',
    label: 'Carto Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; CartoDB',
    subdomains: 'abcd',
    maxZoom: 19,
    color: '#1e293b',
  },
  esriStreet: {
    id: 'esriStreet',
    label: 'ESRI Street',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri',
    subdomains: '',
    maxZoom: 19,
    color: '#2563eb',
  },
  windy: {
    id: 'windy',
    label: 'Weather (Windy)',
    url: 'https://embed.windy.com/embed2.html',
    attribution: '',
    subdomains: '',
    maxZoom: 19,
    color: '#38bdf8',
  },
};

export const DEFAULT_BASEMAP = 'custom';
export const FALLBACK_BASEMAP = 'custom';
export const TILE_ERROR_THRESHOLD = 999;

export const DEFAULT_CENTER = [22.9, 78.9];
export const DEFAULT_ZOOM = 5;
export const MIN_ZOOM = 2;
export const MAX_ZOOM = 19;

export const DRAW_STYLES = {
  default: { color: '#2563eb', weight: 3, fillOpacity: 0.15 },
  selected: { color: '#f59e0b', weight: 4, fillOpacity: 0.20 },
  hover: { color: '#10b981', weight: 3, fillOpacity: 0.25 },
};
