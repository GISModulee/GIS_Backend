// src/state/layersSlice.js
import { createSlice } from "@reduxjs/toolkit";
import { confirmSaveShape } from "./drawingSlice.js";

let _id = 1;
export const tempId = () => `local_${_id++}`;

// Accept optional localId so the hook can pre-generate it before dispatching
const makeLayer = ({ name, color = "#2563eb", type = "group", localId } = {}) => ({
  localId: localId || tempId(),
  backendId: null,
  status: "local",
  name: name || "Auto Layer 1",
  type,
  visible: true,
  color,
  features: [],
  expanded: true,
  error: null,
});

const makeFeature = ({
  name,
  geometry,
  color,
  category,
  layerLocalId,
  type,
  localId,
  backendId = null,
  status = "local",
  feature_number = null,
  case_id = null,
  layer_id = null,
  commentsList = [],
  comments_count = 0,
  hasComments = false,
  visible = true,
  error = null,
}) => ({
  localId: localId || tempId(),
  backendId,
  layerLocalId,
  status,
  name: name || "Untitled Feature",
  type,
  geometry,
  color: color || "#2563eb",
  category: category || "",
  visible,
  error,
  feature_number,
  case_id,
  layer_id,
  commentsList,
  comments_count,
  hasComments,
});

const layersSlice = createSlice({
  name: "layers",
  initialState: {
    items: [],
    selectedLayerId: null,
    selectedFeatureId: null,
    hoveredFeatureId: null,
    backendGeoJson: null,
  },

  reducers: {
    // ── Backend hydration ────────────────────────────────

    // Called on app load — replaces items with backend data
    hydrateFromBackend(state, action) {
      state.items = action.payload;
    },

    // Called after createLayer API returns — writes backendId into the local layer
    setLayerBackendId(state, action) {
      const { localId, backendId } = action.payload;
      const layer = state.items.find((l) => l.localId === localId);
      if (layer) {
        layer.backendId = backendId;
        layer.status = "saved";
      }
    },

    // Called after createFeature API returns — writes backendId and metadata into the local feature
    setFeatureBackendId(state, action) {
      const { layerLocalId, featureLocalId, backendId, feature_number, case_id, layer_id } = action.payload;
      const layer = state.items.find((l) => l.localId === layerLocalId);
      if (!layer) return;
      const feature = layer.features.find((f) => f.localId === featureLocalId);
      if (feature) {
        feature.backendId = backendId;
        feature.feature_number = feature_number;
        feature.case_id = case_id;
        feature.layer_id = layer_id;
        feature.status = "saved";
      }
    },

    setFeatureHasComments(state, action) {
      const { backendId, featureLocalId, hasComments, commentsList, commentsCount } = action.payload;
      for (const layer of state.items) {
        const feature = (layer.features || []).find(
          (f) => (backendId && Number(f.backendId) === Number(backendId)) || (featureLocalId && f.localId === featureLocalId)
        );
        if (feature) {
          feature.hasComments = typeof hasComments === 'boolean' ? hasComments : false;
          feature.comments_count = commentsCount ?? (commentsList ? commentsList.length : 0);
          if (commentsList) feature.commentsList = commentsList;
          break;
        }
      }
    },

    setBackendGeoJson(state, action) {
      state.backendGeoJson = action.payload;
    },

    clearBackendGeoJson(state) {
      state.backendGeoJson = null;
    },

    // ── Layer actions ────────────────────────────────────

    addLayer(state, action) {
      const layer = makeLayer(action.payload); // payload may include localId
      state.items.push(layer);
      state.selectedLayerId = layer.localId;
    },
    addLayerFromBackend(state, action) {
      const layerData = action.payload;
      const localId = `local_${layerData.backendId}`;
      if (state.items.some((l) => l.localId === localId)) return;
      state.items.push({
        localId,
        backendId: layerData.backendId,
        status: "saved",
        name: layerData.name || `Layer ${layerData.backendId}`,
        type: layerData.type || "group",
        visible: layerData.visible ?? true,
        color: layerData.color || "#2563eb",
        features: [],
        expanded: true,
        error: null,
      });
    },
    updateLayer(state, action) {
      const { localId, changes } = action.payload;
      const layer = state.items.find((l) => l.localId === localId);
      if (layer) Object.assign(layer, changes);
    },

    deleteLayer(state, action) {
      state.items = state.items.filter((l) => l.localId !== action.payload);
      if (state.selectedLayerId === action.payload) state.selectedLayerId = null;
    },

    toggleLayerVisible(state, action) {
      const layer = state.items.find((l) => l.localId === action.payload);
      if (layer) layer.visible = !layer.visible;
    },

    toggleLayerExpanded(state, action) {
      const layer = state.items.find((l) => l.localId === action.payload);
      if (layer) layer.expanded = !layer.expanded;
    },

    selectLayer(state, action) {
      state.selectedLayerId = action.payload;
    },

    selectFeature(state, action) {
      const id = action.payload;
      console.log("[layersSlice] selectFeature reducer called with ID:", id);
      if (id && state.selectedFeatureId === id) {
        state.selectedFeatureId = null;
      } else {
        state.selectedFeatureId = id;
        if (id) {
          const layer = state.items.find((l) =>
            l.features.some((f) => f.backendId === id || f.localId === id)
          );
          console.log("[layersSlice] Found parent layer to expand:", layer?.name);
          if (layer) {
            layer.expanded = true;
          }
        }
      }
    },

    setHoveredFeatureId(state, action) {
      state.hoveredFeatureId = action.payload;
    },

    // ── Feature actions ──────────────────────────────────

    addFeature(state, action) {
      const { layerLocalId, featureData } = action.payload;
      let layer = state.items.find((l) => l.localId === layerLocalId);
      if (!layer) {
        layer = {
          localId: layerLocalId,
          backendId: featureData.layer_id,
          status: "saved",
          name: `Layer ${featureData.layer_id}`,
          type: "group",
          visible: true,
          color: "#2563eb",
          features: [],
          expanded: true,
          error: null,
        };
        state.items.push(layer);
      }
      layer.features.push(makeFeature({ ...featureData, layerLocalId }));
    },

    addFeaturesBatch(state, action) {
      const { layerLocalId, featuresData } = action.payload;
      let layer = state.items.find((l) => l.localId === layerLocalId);
      if (!layer) {
        const firstFeature = featuresData[0] || {};
        layer = {
          localId: layerLocalId,
          backendId: firstFeature.layer_id,
          status: "saved",
          name: `Layer ${firstFeature.layer_id}`,
          type: "group",
          visible: true,
          color: "#2563eb",
          features: [],
          expanded: true,
          error: null,
        };
        state.items.push(layer);
      }

      featuresData.forEach((featureData) => {
        const backendId = featureData.backendId || featureData.id;
        const index = layer.features.findIndex(
          (feat) => feat.backendId === backendId || feat.localId === `local_feat_${backendId}`
        );
        if (index === -1) {
          layer.features.push(makeFeature({ ...featureData, layerLocalId }));
        } else {
          layer.features[index] = {
            ...layer.features[index],
            ...makeFeature({ ...featureData, layerLocalId }),
          };
        }
      });
    },

    updateFeature(state, action) {
      const { layerLocalId, featureLocalId, changes } = action.payload;
      const layer = state.items.find((l) => l.localId === layerLocalId);
      if (!layer) return;
      const feature = layer.features.find((f) => f.localId === featureLocalId);
      if (feature) Object.assign(feature, changes);
    },

    deleteFeature(state, action) {
      const { layerLocalId, featureLocalId } = action.payload;
      const layer = state.items.find((l) => l.localId === layerLocalId);
      if (layer) layer.features = layer.features.filter((f) => f.localId !== featureLocalId);
    },

    toggleFeatureVisible(state, action) {
      const { layerLocalId, featureLocalId } = action.payload;
      const layer = state.items.find((l) => l.localId === layerLocalId);
      if (!layer) return;
      const feature = layer.features.find((f) => f.localId === featureLocalId);
      if (feature) feature.visible = !feature.visible;
    },

    moveFeature(state, action) {
      const { featureLocalId, fromLayerLocalId, toLayerLocalId } = action.payload;
      if (fromLayerLocalId === toLayerLocalId) return;
      const fromLayer = state.items.find((l) => l.localId === fromLayerLocalId);
      const toLayer = state.items.find((l) => l.localId === toLayerLocalId);
      if (!fromLayer || !toLayer) return;
      const idx = fromLayer.features.findIndex((f) => f.localId === featureLocalId);
      if (idx === -1) return;
      const [feature] = fromLayer.features.splice(idx, 1);
      feature.layerLocalId = toLayerLocalId;
      toLayer.features.push(feature);
    },
  },

  extraReducers: (builder) => {
    builder.addCase(confirmSaveShape, (state, action) => {
      const { name, category, color, preFeatureLocalId, preLayerLocalId, geometry, type } = action.payload;
      if (!geometry) return;

      let targetLayer = state.items.find((l) => l.localId === state.selectedLayerId);

      if (!targetLayer) {
        // Auto-create a local layer — backend ID written later via setLayerBackendId
        const nextLayerNum = state.items.filter(l => l.name.startsWith("Auto Layer")).length + 1;
        targetLayer = makeLayer({
          localId: preLayerLocalId,
          name: `Auto Layer ${nextLayerNum}`,
          color,
        });
        state.items.push(targetLayer);
      }

      const feature = makeFeature({
        localId: preFeatureLocalId,
        name, geometry, color, category, type,
        layerLocalId: targetLayer.localId,
      });
      targetLayer.features.push(feature);
      targetLayer.expanded = true;

      // Clear selection so the newly saved shape is not selected
      state.selectedFeatureId = null;
      state.selectedLayerId = null;
    });
  }
});

export const {
  hydrateFromBackend,
  setLayerBackendId, setFeatureBackendId, setFeatureHasComments,
  addLayer, addLayerFromBackend, updateLayer, deleteLayer,
  toggleLayerVisible, toggleLayerExpanded, selectLayer, selectFeature, setHoveredFeatureId,
  addFeature, addFeaturesBatch, updateFeature, deleteFeature,
  toggleFeatureVisible, moveFeature,
  setBackendGeoJson, clearBackendGeoJson,
} = layersSlice.actions;

export default layersSlice.reducer;
