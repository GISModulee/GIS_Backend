// src/state/mapSlice.js
import { createSlice } from '@reduxjs/toolkit';
import { DEFAULT_BASEMAP, DEFAULT_CENTER, DEFAULT_ZOOM } from '@/config/apiConfig.js';

const savedBasemap = localStorage.getItem('gis_basemap') || DEFAULT_BASEMAP;

const initialState = {
  basemap: savedBasemap,
  center: DEFAULT_CENTER,
  zoom: DEFAULT_ZOOM,
  drawMode: null,
  measuring: false,
  activeTool: 'select',     // ← new: tracks which toolbar tool is active
  mapInstance: null,        // ← new: holds the live Leaflet map object
};

const mapSlice = createSlice({
  name: 'map',
  initialState,
  reducers: {
    setBasemap(state, action) {
      state.basemap = action.payload;
      localStorage.setItem('gis_basemap', action.payload);
    },

    setViewport(state, action) {
      if (action.payload.center) state.center = action.payload.center;
      if (action.payload.zoom !== undefined) state.zoom = action.payload.zoom;
    },

    setDrawMode(state, action) {
      state.drawMode = action.payload;
    },

    setMeasuring(state, action) {
      state.measuring = action.payload;
    },

    // ← new: set the active toolbar tool
    setActiveTool(state, action) {
      state.activeTool = action.payload;
    },

    // ← new: store the Leaflet map instance
    // Note: Redux recommends not storing non-serializable objects,
    // but Leaflet map instances are safe to store as a ref-like value.
    setMapInstance(state, action) {
      state.mapInstance = action.payload;
    },
  },
});

export const {
  setBasemap,
  setViewport,
  setDrawMode,
  setMeasuring,
  setActiveTool,
  setMapInstance,
} = mapSlice.actions;

export default mapSlice.reducer;
