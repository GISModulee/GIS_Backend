import axiosInstance from "@/api/axiosInstance.js";

const layerService = {
  getAllForCase: async (caseId = null) => {
    const { data } = await axiosInstance.get(caseId ? `/layers/case/${caseId}` : "/layers");
    return data;
  },


  updateLayer: async (layerId, payload) => {
    const { data } = await axiosInstance.patch(`/layers/${layerId}`, payload);
    return data;
  },

  deleteLayer: async (layerId) => {
    await axiosInstance.delete(`/layers/${layerId}`);
  },

  createFeature: async (payload) => {
    const { data } = await axiosInstance.post("/features", payload);
    return data;
  },

  updateFeature: async (featureId, payload) => {
    const { data } = await axiosInstance.patch(`/features/${featureId}`, payload);
    return data;
  },

  replaceFeature: async (featureId, payload) => {
    const { data } = await axiosInstance.put(`/features/${featureId}`, payload);
    return data;
  },

  deleteFeature: async (featureId) => {
    await axiosInstance.delete(`/features/${featureId}`);
  },

  getFeaturesByLayer: async (layerId) => {
    const { data } = await axiosInstance.get(`/layers/${layerId}/features`);
    return data;
  },

  getAllFeatures: async () => {
    const { data } = await axiosInstance.get("/features");
    return data;
  },

  // Replace addComment and add getCommentImage
  addComment: async (caseId, featureNumber, comment, imageFile = null) => {
    /*
    const formData = new FormData();
    formData.append("case_id", caseId);
    formData.append("feature_number", featureNumber);
    formData.append("comment", comment);
    if (imageFile) {
      formData.append("attachment", imageFile);
    }

    const { data } = await axiosInstance.post("/comments", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
    */
    return { status: "success", message: "Comment saved (mocked)" };
  },

  getComments: async (caseId, featureNumber) => {
    /*
    const { data } = await axiosInstance.get(`/cases/${caseId}/features/${featureNumber}/comments`);
    return data;
    */
    return [];
  },

  // src/api/layerService.js

  getCommentImage: async (commentId) => {
    /*
    const response = await axiosInstance.get(`/comments/${commentId}/attachment`, {
      responseType: "blob",
    });

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(response.data);
    });
    */
    return null;
  },
  // GET /layers (no case_id)
  getAllLayers: async () => {
    const { data } = await axiosInstance.get("/layers");
    return data;
  },

  createLayer: async (payload) => {
    const { data } = await axiosInstance.post(
      "/layers",
      payload
    );
    return data;
  },

  getCases: async () => {
    const { data } = await axiosInstance.get("/cases");
    return data;
  },

  getCaseById: async (caseId) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}`);
    return data;
  },

  replaceLayer: async (layerId, payload) => {
    if (payload.case_id !== undefined) {
      const { data } = await axiosInstance.put(`/layers/${layerId}`, {
        case_id: payload.case_id,
        name: payload.name,
        layer_type: payload.layer_type || "group",
        visible: payload.visible ?? true,
      });
      return data;
    } else {
      const { data } = await axiosInstance.patch(`/layers/${layerId}`, {
        name: payload.name,
      });
      return data;
    }
  },

  runUnion: async (payload) => {
    const { data } = await axiosInstance.post("/vector/union", payload);
    return data;
  },

  runIntersection: async (payload) => {
    const { data } = await axiosInstance.post("/vector/intersection", payload);
    return data;
  },

  runDifference: async (payload) => {
    const { data } = await axiosInstance.post("/vector/difference", payload);
    return data;
  },

  runBuffer: async (payload) => {
    const { data } = await axiosInstance.post("/vector/buffer", payload);
    return data;
  },

  runSymmetricDifference: async (payload) => {
    const { data } = await axiosInstance.post("/vector/symdifference", payload);
    return data;
  },

  runCentroid: async (payload) => {
    const { data } = await axiosInstance.post("/vector/centroid", payload);
    return data;
  },

  runConvexHull: async (payload) => {
    const { data } = await axiosInstance.post("/vector/convex-hull", payload);
    return data;
  },

  getFeaturesByCase: async (caseId) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/features`);
    return data;
  },
};

export default layerService;
