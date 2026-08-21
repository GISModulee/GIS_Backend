// src/state/store.js
import { configureStore } from "@reduxjs/toolkit";
import mapReducer    from "./mapSlice.js";
import layersReducer from "./layersSlice.js";
import drawingReducer from "./drawingSlice.js";
import resultLayersReducer from "./resultLayersSlice.js";
import authReducer   from "./authSlice.js";

export const store = configureStore({
  reducer: {
    map:          mapReducer,
    layers:       layersReducer,
    drawing:      drawingReducer,
    resultLayers: resultLayersReducer,
    auth:         authReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredPaths:   ["map.mapInstance"],
        ignoredActions: ["map/setMapInstance"],
      },
    }),
});