import { createSlice } from "@reduxjs/toolkit";

const drawingSlice = createSlice({
  name: "drawing",
  initialState: {
    pendingGeometry: null,
    pendingType: null,
    pendingColor: "#2563eb",
    commentModal: {
      open: false,
      featureBackendId: null,
    },
    deleteConfirm: {
      open: false,
      type: null,
      targetId: null,
      backendId: null,
      layerLocalId: null,
      name: "",
      featuresList: [],
    },
  },
  reducers: {
    setPendingGeometry(state, action) {
      state.pendingGeometry = action.payload.geometry;
      state.pendingType = action.payload.type;
      state.pendingColor = action.payload.color || "#2563eb";
    },
    clearPendingGeometry(state) {
      state.pendingGeometry = null;
      state.pendingType = null;
      state.pendingColor = "#2563eb";
    },
    confirmSaveShape(state) {
      state.pendingGeometry = null;
      state.pendingType = null;
      state.pendingColor = "#2563eb";
    },
    openCommentModal(state, action) {
      state.commentModal = { open: true, featureBackendId: action.payload };
    },
    closeCommentModal(state) {
      state.commentModal = { open: false, featureBackendId: null };
    },
    openDeleteConfirm(state, action) {
      const { type, targetId, backendId, layerLocalId, name, featuresList } = action.payload;
      state.deleteConfirm = {
        open: true,
        type,
        targetId,
        backendId,
        layerLocalId,
        name,
        featuresList: featuresList || [],
      };
    },
    closeDeleteConfirm(state) {
      state.deleteConfirm = {
        open: false,
        type: null,
        targetId: null,
        backendId: null,
        layerLocalId: null,
        name: "",
        featuresList: [],
      };
    },
  },
});

export const {
  setPendingGeometry,
  clearPendingGeometry,
  confirmSaveShape,
  openCommentModal,
  closeCommentModal,
  openDeleteConfirm,
  closeDeleteConfirm,
} = drawingSlice.actions;

export default drawingSlice.reducer;
