import { layersClient } from "@/api/client.js";
import { API_ENDPOINTS } from "@/config/apiConfig.js";

const layerService = {
  getAllForCase: async (caseId = null) => {
    const { data } = await layersClient.get(API_ENDPOINTS.CASES.LAYERS(caseId));
    return data;
  },


  updateLayer: async (layerId, payload) => {
    const { data } = await layersClient.patch(API_ENDPOINTS.LAYERS.BY_ID(layerId), payload);
    return data;
  },

  deleteLayer: async (layerId) => {
    await layersClient.delete(API_ENDPOINTS.LAYERS.BY_ID(layerId));
  },

  createFeature: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.FEATURES.ALL, payload);
    return data;
  },

  updateFeature: async (featureId, payload) => {
    const { data } = await layersClient.patch(API_ENDPOINTS.FEATURES.BY_ID(featureId), payload);
    return data;
  },

  replaceFeature: async (featureId, payload) => {
    const { data } = await layersClient.put(API_ENDPOINTS.FEATURES.BY_ID(featureId), payload);
    return data;
  },

  deleteFeature: async (featureId) => {
    await layersClient.delete(API_ENDPOINTS.FEATURES.BY_ID(featureId));
  },

  getFeaturesByLayer: async (layerId) => {
    const { data } = await layersClient.get(API_ENDPOINTS.FEATURES.BY_LAYER(layerId));
    return data;
  },

  getAllFeatures: async () => {
    const { data } = await layersClient.get(API_ENDPOINTS.FEATURES.ALL);
    return data;
  },

  // Replace addComment and add getCommentImage
  addComment: async (featureId, comment, userId = 1, imageFile = null) => {
    const formData = new FormData();
    formData.append("feature_id", featureId);
    formData.append("user_id", userId);
    formData.append("comment", comment);
    if (imageFile) {
      formData.append("image", imageFile);
      formData.append("attachment", imageFile);
      formData.append("file", imageFile);
    }

    const { data } = await layersClient.post(API_ENDPOINTS.COMMENTS.CREATE, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  getComments: async (featureId) => {
    const { data } = await layersClient.get(API_ENDPOINTS.COMMENTS.BY_FEATURE(featureId));
    return data;
  },

  // src/api/layerService.js

  getCommentImage: async (commentId) => {
    const response = await layersClient.get(`/comments/${commentId}/attachment`, {
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
    const { data } = await layersClient.get(API_ENDPOINTS.LAYERS.ALL);
    return data;
  },

  createLayer: async (payload) => {
    const { data } = await layersClient.post(
      API_ENDPOINTS.LAYERS.ALL,
      payload
    );
    return data;
  },

  getCases: async () => {
    const { data } = await layersClient.get(API_ENDPOINTS.CASES.ALL);
    return data;
  },

  getCaseById: async (caseId) => {
    const { data } = await layersClient.get(API_ENDPOINTS.CASES.BY_ID(caseId));
    return data;
  },

  replaceLayer: async (layerId, payload) => {
    if (payload.case_id !== undefined) {
      const { data } = await layersClient.put(API_ENDPOINTS.LAYERS.BY_ID(layerId), {
        case_id: payload.case_id,
        name: payload.name,
        layer_type: payload.layer_type || "group",
        visible: payload.visible ?? true,
      });
      return data;
    } else {
      const { data } = await layersClient.patch(API_ENDPOINTS.LAYERS.BY_ID(layerId), {
        name: payload.name,
      });
      return data;
    }
  },

  runUnion: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.UNION, payload);
    return data;
  },

  runIntersection: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.INTERSECTION, payload);
    return data;
  },

  runDifference: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.DIFFERENCE, payload);
    return data;
  },

  runBuffer: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.BUFFER, payload);
    return data;
  },

  runSymmetricDifference: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.SYM_DIFFERENCE, payload);
    return data;
  },

  runCentroid: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.CENTROID, payload);
    return data;
  },

  runConvexHull: async (payload) => {
    const { data } = await layersClient.post(API_ENDPOINTS.VECTOR.CONVEX_HULL, payload);
    return data;
  },
};

export default layerService;
