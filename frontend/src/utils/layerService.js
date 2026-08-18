import axiosInstance from "@/api/axiosInstance.js";

const layerService = {
  getAllForCase: async (caseId = null) => {
    const { data } = await axiosInstance.get(caseId ? `/layers/case/${caseId}` : "/layers");
    return data;
  },


  updateLayer: async (caseId, layerId, payload) => {
    const { data } = await axiosInstance.patch(`/layers/case/${caseId}/${layerId}`, payload);
    return data;
  },

  deleteLayer: async (caseId, layerId) => {
    const { data } = await axiosInstance.delete(`/layers/case/${caseId}/${layerId}`);
    return data;
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

  editFeatureInLayer: async (caseId, layerId, featureId, payload) => {
    const { data } = await axiosInstance.put(`/cases/${caseId}/layers/${layerId}/features/${featureId}`, payload);
    return data;
  },

  editFeaturePartialInLayer: async (caseId, layerId, featureId, payload) => {
    const { data } = await axiosInstance.patch(`/cases/${caseId}/layers/${layerId}/features/${featureId}`, payload);
    return data;
  },

  deleteFeature: async (caseId, layerId, featureId) => {
    const { data } = await axiosInstance.delete(`/cases/${caseId}/layers/${layerId}/features/${featureId}`);
    return data;
  },
  getGeoclipFeatures: async (layerId) => {
    const { data } = await axiosInstance.get(`/geoclip/layers/${layerId}/features`);
    return data;
  },
  deleteGeoclipLayer: async (layerId) => {
    const { data } = await axiosInstance.delete(`/geoclip/layers/${layerId}`);
    return data;
  },

  getFeaturesByLayer: async (caseId, layerId) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/layers/${layerId}/features`);
    return data;
  },

  getFeaturesByCase: async (caseId) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/features`);
    return data;
  },

  getSingleFeature: async (caseId, layerId, featureNumber) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/layers/${layerId}/features/${featureNumber}`);
    return data;
  },

  getAllFeatures: async () => {
    const { data } = await axiosInstance.get("/features");
    return data;
  },

  // Add comment to a feature
  addComment: async (caseId, layerId, featureNumber, comment, imageFile = null) => {
    const parsedNum = parseInt(featureNumber, 10);
    const formData = new FormData();
    formData.append("case_id", caseId);
    formData.append("layer_id", layerId);
    formData.append("feature_number", Number.isFinite(parsedNum) ? parsedNum : featureNumber);
    formData.append("comment", comment);
    if (imageFile) {
      formData.append("attachment", imageFile);
    }

    const { data } = await axiosInstance.post(`/cases/${caseId}/layers/${layerId}/comments`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  getComments: async (caseId, layerId, featureNumber) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/layers/${layerId}/features/${featureNumber}/comments`);
    return data;
  },

  getCommentsThread: async (caseId, layerId, featureNumber) => {
    const { data } = await axiosInstance.get(`/cases/${caseId}/layers/${layerId}/features/${featureNumber}/comments/thread`);
    return data;
  },

  addReply: async (caseId, layerId, featureNumber, parentCommentId, comment, imageFile = null) => {
    const formData = new FormData();
    formData.append("case_id", caseId);
    formData.append("layer_id", layerId);
    formData.append("parent_comment_id", parentCommentId);
    formData.append("comment", comment);
    if (imageFile) {
      formData.append("attachment", imageFile);
    }
    const { data } = await axiosInstance.post(
      `/cases/${caseId}/layers/${layerId}/features/${featureNumber}/comments/reply`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return data;
  },

  getCommentImage: async (caseId, layerId, featureNumber, commentId) => {
    const response = await axiosInstance.get(`/cases/${caseId}/layers/${layerId}/features/${featureNumber}/comments/${commentId}/attachment`, {
      responseType: "blob",
    });

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(response.data);
    });
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
    const caseId = payload.case_id || 1;
    const { data } = await axiosInstance.put(`/layers/case/${caseId}/${layerId}`, {
      case_id: caseId,
      name: payload.name,
      layer_type: payload.layer_type || "group",
      visible: payload.visible ?? true,
    });
    return data;
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
};

export default layerService;
