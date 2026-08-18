import { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import { addFeature, addFeaturesBatch, updateFeature, deleteFeature, addLayerFromBackend, updateLayer, deleteLayer } from "@/state/layersSlice.js";
import { API_URLS } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";

export default function FeatureWebSocket({ caseId }) {
  const dispatch = useDispatch();
  const items = useSelector((s) => s.layers.items);
  const itemsRef = useRef(items);
  const pendingFeaturesRef = useRef([]);
  const batchBufferRef = useRef({});
  const bufferTimerRef = useRef(null);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  const flushBuffer = () => {
    Object.keys(batchBufferRef.current).forEach((layerLocalId) => {
      const features = batchBufferRef.current[layerLocalId];
      if (features.length > 0) {
        console.log(`[FeatureWS] Flushing batch of ${features.length} features for layer ${layerLocalId}`);
        dispatchFeatureBatchCreated(layerLocalId, features);
      }
    });
    batchBufferRef.current = {};
    bufferTimerRef.current = null;
  };

  const dispatchFeatureCreated = (layerLocalId, f) => {
    let geometry = f.geometry;
    if (typeof geometry === "string") {
      try {
        geometry = JSON.parse(geometry);
      } catch (_) {}
    }

    let properties = f.properties || {};
    if (typeof properties === "string") {
      try {
        properties = JSON.parse(properties);
      } catch (_) {}
    }

    // Swap coordinate order if backend returned [latitude, longitude] (out of bounds for India)
    if (geometry?.type === "Point" && Array.isArray(geometry.coordinates) && geometry.coordinates.length === 2) {
      const [c0, c1] = geometry.coordinates;
      if (c0 >= 5 && c0 <= 40 && c1 >= 60 && c1 <= 100) {
        geometry = {
          ...geometry,
          coordinates: [c1, c0],
        };
      }
    }

    const isCircleFeature = f.geometry_type === "Circle" || properties.type === "circle";
    if (isCircleFeature && geometry?.type === "Point") {
      geometry = {
        ...geometry,
        radius: f.radius || properties.radius || 1000,
      };
    }

    const type = isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

    dispatch(addFeature({
      layerLocalId,
      featureData: {
        localId: `local_feat_${f.id}`,
        backendId: f.id,
        feature_number: f.feature_number,
        case_id: f.case_id,
        layer_id: f.layer_id,
        status: "saved",
        name: f.name,
        type,
        geometry_type: f.geometry_type,
        center: f.center || properties.center,
        radius: f.radius || properties.radius,
        geometry: geometry,
        properties: properties,
        color: properties.color || f.color || "#2563eb",
        category: properties.category || f.category || "",
        commentsList: [],
        comments_count: 0,
        hasComments: false,
      }
    }));
  };

  const dispatchFeatureBatchCreated = (layerLocalId, rawFeatures) => {
    if (!Array.isArray(rawFeatures)) return;

    const normalizedFeatures = rawFeatures.map((f) => {
      let geometry = f.geometry;
      if (typeof geometry === "string") {
        try {
          geometry = JSON.parse(geometry);
        } catch (_) {}
      }

      let properties = f.properties || {};
      if (typeof properties === "string") {
        try {
          properties = JSON.parse(properties);
        } catch (_) {}
      }

      // Swap coordinate order if backend returned [latitude, longitude] (out of bounds for India)
      if (geometry?.type === "Point" && Array.isArray(geometry.coordinates) && geometry.coordinates.length === 2) {
        const [c0, c1] = geometry.coordinates;
        if (c0 >= 5 && c0 <= 40 && c1 >= 60 && c1 <= 100) {
          geometry = {
            ...geometry,
            coordinates: [c1, c0],
          };
        }
      }

      const isCircleFeature = f.geometry_type === "Circle" || properties.type === "circle";
      if (isCircleFeature && geometry?.type === "Point") {
        geometry = {
          ...geometry,
          radius: f.radius || properties.radius || 1000,
        };
      }

      const type = isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

      return {
        localId: `local_feat_${f.id}`,
        backendId: f.id,
        feature_number: f.feature_number,
        case_id: f.case_id,
        layer_id: f.layer_id,
        status: "saved",
        name: f.name,
        type,
        geometry_type: f.geometry_type,
        center: f.center || properties.center,
        radius: f.radius || properties.radius,
        geometry: geometry,
        properties: properties,
        color: properties.color || f.color || "#2563eb",
        category: properties.category || f.color || "",
        commentsList: [],
        comments_count: 0,
        hasComments: false,
      };
    });

    dispatch(addFeaturesBatch({
      layerLocalId,
      featuresData: normalizedFeatures,
    }));
  };

  const dispatchFeatureUpdated = (layerLocalId, featureLocalId, f) => {
    let geometry = f.geometry;
    if (typeof geometry === "string") {
      try {
        geometry = JSON.parse(geometry);
      } catch (_) {}
    }

    let properties = f.properties || {};
    if (typeof properties === "string") {
      try {
        properties = JSON.parse(properties);
      } catch (_) {}
    }

    // Swap coordinate order if backend returned [latitude, longitude] (out of bounds for India)
    if (geometry?.type === "Point" && Array.isArray(geometry.coordinates) && geometry.coordinates.length === 2) {
      const [c0, c1] = geometry.coordinates;
      if (c0 >= 5 && c0 <= 40 && c1 >= 60 && c1 <= 100) {
        geometry = {
          ...geometry,
          coordinates: [c1, c0],
        };
      }
    }

    const isCircleFeature = f.geometry_type === "Circle" || properties.type === "circle";
    if (isCircleFeature && geometry?.type === "Point") {
      geometry = {
        ...geometry,
        radius: f.radius || properties.radius || 1000,
      };
    }

    const type = isCircleFeature ? "circle" : (geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

    dispatch(updateFeature({
      layerLocalId,
      featureLocalId,
      changes: {
        name: f.name,
        type,
        geometry_type: f.geometry_type,
        center: f.center || properties.center,
        radius: f.radius || properties.radius,
        geometry: geometry,
        properties: properties,
        color: properties.color || f.color || "#2563eb",
        category: properties.category || f.category || "",
      }
    }));
  };

  // Process pending queued features when items list updates in Redux
  useEffect(() => {
    if (pendingFeaturesRef.current.length === 0) return;

    const remaining = [];
    pendingFeaturesRef.current.forEach((item) => {
      const layerExists = items.some((l) => l.localId === item.layerLocalId);
      if (layerExists) {
        if (item.type === "batch") {
          console.log("[FeatureWS] Dequeuing and adding pending batch:", item.features.length, "features");
          dispatchFeatureBatchCreated(item.layerLocalId, item.features);
        } else {
          const f = item.feature;
          const alreadyExists = items.some((layer) =>
            (layer.features || []).some((feat) => feat.backendId === f.id || feat.localId === `local_feat_${f.id}`)
          );
          if (!alreadyExists) {
            console.log("[FeatureWS] Dequeuing and adding pending feature:", f.id);
            dispatchFeatureCreated(item.layerLocalId, f);
          }
        }
      } else {
        remaining.push(item);
      }
    });

    pendingFeaturesRef.current = remaining;
  }, [items, dispatch]);

  useEffect(() => {
    if (!caseId) return;

    let socket = null;
    let reconnectTimeoutId = null;
    let reconnectDelay = 1000;
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) return;

      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("access_token") ||
        "";

      if (!token) {
        console.error("[FeatureWS] Access token is missing.");
        return;
      }

      const websocketUrl = new URL(
        API_URLS.LAYERS,
        window.location.origin
      );

      websocketUrl.protocol =
        websocketUrl.protocol === "https:"
          ? "wss:"
          : "ws:";

      websocketUrl.pathname = `/ws/cases/${caseId}/features`;
      websocketUrl.search = `?token=${encodeURIComponent(token)}`;

      console.log("[FeatureWS] Connecting to:", websocketUrl.toString());

      socket = new WebSocket(websocketUrl.toString());

      socket.onopen = () => {
        console.log("[FeatureWS] Connected for case:", caseId);
        reconnectDelay = 1000;
      };

      socket.onmessage = async (event) => {
        if (isUnmounted) return;

        try {
          const message = JSON.parse(event.data);
          console.log("[FeatureWS Debug] Incoming message:", message);

          if (message.event === "connection.ready") {
            return;
          }

          if (message.event === "layer.created" && message.layer) {
            dispatch(addLayerFromBackend({
              backendId: message.layer.id,
              name: message.layer.name,
              type: message.layer.layer_type,
              visible: message.layer.visible,
              color: message.layer.color,
            }));
            return;
          }

          if (message.event === "layer.updated" && message.layer) {
            const localId = `local_${message.layer.id}`;
            const changes = {};
            if (message.layer.name !== undefined) changes.name = message.layer.name;
            if (message.layer.layer_type !== undefined) changes.type = message.layer.layer_type;
            if (message.layer.visible !== undefined) changes.visible = message.layer.visible;
            if (message.layer.color !== undefined) changes.color = message.layer.color;

            dispatch(updateLayer({
              localId,
              changes,
            }));
            return;
          }

          if (message.event === "layer.deleted" && message.layer_id) {
            dispatch(deleteLayer(`local_${message.layer_id}`));
            return;
          }

          if (message.event === "feature.comment_created") {
            const targetLayer = itemsRef.current.find(
              (l) => Number(l.backendId) === Number(message.layer_id) || l.localId === `local_${message.layer_id}`
            );
            if (targetLayer) {
              const targetFeature = (targetLayer.features || []).find(
                (f) => Number(f.feature_number) === Number(message.feature_number)
              );
              if (targetFeature) {
                dispatch(updateFeature({
                  layerLocalId: targetLayer.localId,
                  featureLocalId: targetFeature.localId,
                  changes: {
                    hasComments: true,
                  }
                }));
              }
            }
            return;
          }

          const resolvedLayerId = message.layer_id || message.feature?.layer_id || message.layer?.id;
          if (!resolvedLayerId) return;

          const layerLocalId = `local_${resolvedLayerId}`;
          let layerExists = itemsRef.current.some((l) => l.localId === layerLocalId);

          if (!layerExists && (message.layer_id || message.feature?.layer_id)) {
            try {
              const resolvedCaseId = message.case_id || message.feature?.case_id;
              if (resolvedCaseId) {
                const allLayers = await layerService.getAllForCase(resolvedCaseId);
                const backendLayer = allLayers.find((l) => l.id === resolvedLayerId);
                if (backendLayer) {
                  dispatch(addLayerFromBackend({
                    backendId: backendLayer.id,
                    name: backendLayer.name,
                    type: backendLayer.layer_type,
                    visible: backendLayer.visible,
                    color: backendLayer.color,
                  }));
                  layerExists = true;
                }
              }
            } catch (err) {
              console.error("[FeatureWS] Failed to fetch new layer:", resolvedLayerId, err);
            }
          }

          if (message.event === "feature.created" && message.feature) {
            const f = message.feature;
            const currentLayerExists = itemsRef.current.some((l) => l.localId === layerLocalId);
            if (currentLayerExists) {
              const alreadyExists = itemsRef.current.some((layer) =>
                (layer.features || []).some((feat) => feat.backendId === f.id || feat.localId === `local_feat_${f.id}`)
              );
              if (!alreadyExists) {
                if (!batchBufferRef.current[layerLocalId]) {
                  batchBufferRef.current[layerLocalId] = [];
                }
                batchBufferRef.current[layerLocalId].push(f);

                if (!bufferTimerRef.current) {
                  bufferTimerRef.current = setTimeout(() => {
                    flushBuffer();
                  }, 100);
                }
              }
            } else {
              console.log("[FeatureWS] Layer not found, queuing feature:", f.id);
              pendingFeaturesRef.current.push({ type: "single", layerLocalId, feature: f });
            }
          }

          if (message.event === "feature.batch_created" && Array.isArray(message.features)) {
            const currentLayerExists = itemsRef.current.some((l) => l.localId === layerLocalId);
            if (currentLayerExists) {
              dispatchFeatureBatchCreated(layerLocalId, message.features);
            } else {
              console.log("[FeatureWS] Layer not found, queuing batch:", message.features.length, "features");
              pendingFeaturesRef.current.push({ type: "batch", layerLocalId, features: message.features });
            }
          }

          if (message.event === "feature.updated" && message.feature) {
            const f = message.feature;
            const featureLocalId = `local_feat_${f.id}`;
            const exists = itemsRef.current.some((layer) =>
              (layer.features || []).some((feat) => feat.backendId === f.id || feat.localId === featureLocalId)
            );

            if (exists) {
              dispatchFeatureUpdated(layerLocalId, featureLocalId, f);
            }
          }

          if (message.event === "feature.deleted" && message.feature_id) {
            const featureLocalId = `local_feat_${message.feature_id}`;
            const exists = itemsRef.current.some((layer) =>
              (layer.features || []).some((feat) => feat.backendId === message.feature_id || feat.localId === featureLocalId)
            );

            if (exists) {
              dispatch(deleteFeature({
                layerLocalId,
                featureLocalId,
              }));
            }
          }
        } catch (error) {
          console.error("[FeatureWS] Failed to process message:", error);
        }
      };

      socket.onclose = (event) => {
        console.log(`[FeatureWS] Closed for case ${caseId}. Code: ${event.code}`);
        if (isUnmounted) return;

        if (event.code === 1008) {
          console.error("[FeatureWS] Authentication failed. Reconnect disabled.");
          return;
        }

        const delay = reconnectDelay;
        console.log(`[FeatureWS] Reconnecting in ${delay}ms...`);
        reconnectTimeoutId = window.setTimeout(connect, delay);
        reconnectDelay = Math.min(reconnectDelay * 2, 16000);
      };

      socket.onerror = (error) => {
        console.error("[FeatureWS] Connection error:", error);
        try {
          socket.close();
        } catch (_) { }
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimeoutId) window.clearTimeout(reconnectTimeoutId);
      if (bufferTimerRef.current) window.clearTimeout(bufferTimerRef.current);
      if (socket) {
        console.log("[FeatureWS] Cleaning up socket for case:", caseId);
        socket.onclose = null;
        try {
          socket.close();
        } catch (_) { }
      }
    };
  }, [caseId, dispatch]);

  return null;
}
