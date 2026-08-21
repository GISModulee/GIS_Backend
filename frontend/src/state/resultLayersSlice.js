import { createSlice } from "@reduxjs/toolkit";

const resultLayersSlice = createSlice({
  name: "resultLayers",
  initialState: {
    resultLayers: [],
  },
  reducers: {
    addResultLayer(state, action) {
      state.resultLayers = state.resultLayers.filter(r => r.name !== action.payload.name);
      state.resultLayers.push(action.payload);
    },
    removeResultLayer(state, action) {
      state.resultLayers = state.resultLayers.filter(r => r.id !== action.payload);
    },
    toggleResultLayerVisibility(state, action) {
      const r = state.resultLayers.find(r => r.id === action.payload);
      if (r) r.visible = !r.visible;
    },
  },
});

export const {
  addResultLayer,
  removeResultLayer,
  toggleResultLayerVisibility,
} = resultLayersSlice.actions;

export default resultLayersSlice.reducer;
