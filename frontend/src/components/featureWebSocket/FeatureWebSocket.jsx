import { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import { addFeature, updateFeature, deleteFeature, addLayerFromBackend } from "@/state/layersSlice.js";
import { API_URLS } from "@/config/apiConfig.js";
import layerService from "@/utils/layerService.js";

export default function FeatureWebSocket({ caseId }) {
  const dispatch = useDispatch();
  const items = useSelector((s) => s.layers.items);
  const itemsRef = useRef(items);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

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
          console.log("[FeatureWS] Received message:", message);

          if (message.event === "connection.ready") {
            return;
          }

          const layerLocalId = `local_${message.layer_id}`;
          const layerExists = itemsRef.current.some((l) => l.localId === layerLocalId);
          if (!layerExists && message.layer_id) {
            try {
              const allLayers = await layerService.getAllForCase(message.case_id);
              console.log("[FeatureWS] Fetched layers to find missing one:", allLayers);
              const backendLayer = allLayers.find((l) => l.id === message.layer_id);
              if (backendLayer) {
                dispatch(addLayerFromBackend({
                  backendId: backendLayer.id,
                  name: backendLayer.name,
                  type: backendLayer.layer_type,
                  visible: backendLayer.visible,
                  color: backendLayer.color,
                }));
              }
            } catch (err) {
              console.error("[FeatureWS] Failed to fetch new layer:", message.layer_id, err);
            }
          }
          console.log("[DEBUG] Looking for layer:", layerLocalId, "Available layers:", itemsRef.current.map(l => l.localId));
          if (message.event === "feature.created" && message.feature) {
            const f = message.feature;
            const alreadyExists = itemsRef.current.some((layer) =>
              (layer.features || []).some((feat) => feat.backendId === f.id || feat.localId === `local_feat_${f.id}`)
            );

            if (!alreadyExists) {
              const isCircleFeature = f.geometry_type === "Circle" || f.properties?.type === "circle";
              const type = isCircleFeature ? "circle" : (f.geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

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
                  center: f.center || f.properties?.center,
                  radius: f.radius || f.properties?.radius,
                  geometry: f.geometry,
                  properties: f.properties || {},
                  color: f.properties?.color || f.color || "#2563eb",
                  category: f.properties?.category || f.category || "",
                  commentsList: [],
                  comments_count: 0,
                  hasComments: false,
                }
              }));
            }
          }

          if (message.event === "feature.updated" && message.feature) {
            const f = message.feature;
            const featureLocalId = `local_feat_${f.id}`;
            const exists = itemsRef.current.some((layer) =>
              (layer.features || []).some((feat) => feat.backendId === f.id || feat.localId === featureLocalId)
            );

            if (exists) {
              const isCircleFeature = f.geometry_type === "Circle" || f.properties?.type === "circle";
              const type = isCircleFeature ? "circle" : (f.geometry?.type === "Polygon" ? "polygon" : (f.geometry_type?.toLowerCase() || "polygon"));

              dispatch(updateFeature({
                layerLocalId,
                featureLocalId,
                changes: {
                  name: f.name,
                  type,
                  geometry_type: f.geometry_type,
                  center: f.center || f.properties?.center,
                  radius: f.radius || f.properties?.radius,
                  geometry: f.geometry,
                  properties: f.properties || {},
                  color: f.properties?.color || f.color || "#2563eb",
                  category: f.properties?.category || f.category || "",
                }
              }));
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
