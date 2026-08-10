import { useEffect } from "react";
import { useDispatch } from "react-redux";
import layerService from "@/utils/layerService.js";
import { API_URLS } from "@/config/apiConfig.js";
import { buildCommentPopupHTML } from "@/utils/CommentPopupBuilder.js";
import { setFeatureHasComments } from "@/state/layersSlice.js";

export default function CommentWebSocket({
  selectedFeatureId,
  items,
  itemsRef,
  commentRefs,
  user,
  loadLayersFromBackend,
}) {
  const dispatch = useDispatch();

  useEffect(() => {
    let socket = null;
    let reconnectTimeoutId = null;
    let reconnectDelay = 1000;
    let isUnmounted = false;

    const featureId = Number(selectedFeatureId);

    if (!featureId || Number.isNaN(featureId)) {
      return undefined;
    }

    const allFeatures = items.flatMap((layer) => layer.features || []);
    const featureObj = allFeatures.find(
      (f) => f.backendId === featureId || f.localId === featureId
    );
    const caseId = featureObj?.case_id;
    const layerId = featureObj?.layer_id || 16;
    const featureNumber = featureObj?.feature_number;

    if (!caseId || !featureNumber) {
      return undefined;
    }

    const connect = () => {
      if (isUnmounted) {
        return;
      }

      const token =
        localStorage.getItem("token") ||
        localStorage.getItem("access_token") ||
        "";

      if (!token) {
        console.error("[WebSocket] Access token is missing.");
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

      websocketUrl.pathname =
        `/ws/cases/${caseId}/layers/${layerId}/features/${featureNumber}/comments`;

      websocketUrl.search =
        `?token=${encodeURIComponent(token)}`;

      console.log(
        "[WebSocket] Connecting to:",
        websocketUrl.toString()
      );

      socket = new WebSocket(websocketUrl.toString());

      socket.onopen = () => {
        console.log(
          "[WebSocket] Connected for feature:",
          featureId
        );
        reconnectDelay = 1000;
      };

      socket.onmessage = async (event) => {
        if (isUnmounted) {
          return;
        }

        try {
          const message = JSON.parse(event.data);

          console.log("[WebSocket] Received:", message);

          if (message.event === "connection.ready") {
            console.log(
              "[WebSocket] Subscription ready for feature:",
              message.feature_id
            );
            return;
          }

          if (
            message.event !== "comment.created" ||
            Number(message.feature_number) !== Number(featureNumber)
          ) {
            return;
          }

          console.log(
            "[WebSocket] New comment detected:",
            message.comment_id
          );

          const rawComments =
            await layerService.getCommentsThread(caseId, layerId, featureNumber);

          if (isUnmounted) {
            return;
          }

          const updatedCommentsList = await Promise.all(
            rawComments.map(async (comment) => {
              let attachmentSource = null;

              if (comment.has_attachment || comment.has_image || comment.image_id || comment.image || comment.attachment) {
                try {
                  attachmentSource =
                    await layerService.getCommentImage(
                      caseId,
                      layerId,
                      featureNumber,
                      comment.id
                    );
                } catch (error) {
                  console.warn(
                    "[WebSocket] Failed to load attachment:",
                    comment.id,
                    error
                  );
                }
              }

              return {
                ...comment,
                imgSrc: attachmentSource,
              };
            })
          );

          if (isUnmounted) {
            return;
          }

          const localId = itemsRef.current
            .flatMap((layer) => layer.features || [])
            .find(
              (feature) =>
                Number(feature.backendId) === featureId ||
                Number(feature.id) === featureId
            )
            ?.localId;

          const marker = localId
            ? commentRefs.current[localId]
            : null;

          if (marker?.isPopupOpen()) {
            marker.setPopupContent(
              buildCommentPopupHTML(
                updatedCommentsList,
                featureId,
                user
              )
            );
          }

          await loadLayersFromBackend();
        } catch (error) {
          console.error(
            "[WebSocket] Failed to process message:",
            error
          );
        }
      };

      socket.onclose = (event) => {
        console.log(
          `[WebSocket] Closed for feature ${featureId}.`,
          `Code: ${event.code}`,
          `Reason: ${event.reason}`
        );

        if (isUnmounted) {
          return;
        }

        if (event.code === 1008) {
          console.error(
            "[WebSocket] Authentication failed. Connection will not reconnect."
          );
          return;
        }

        const delay = reconnectDelay;

        console.log(`[WebSocket] Reconnecting in ${delay}ms...`);

        reconnectTimeoutId = window.setTimeout(connect, delay);

        reconnectDelay = Math.min(reconnectDelay * 2, 16000);
      };

      socket.onerror = (error) => {
        console.error("[WebSocket] Connection error:", error);
        try {
          socket.close();
        } catch (closeError) {
          console.error("[WebSocket] Failed to close socket:", closeError);
        }
      };
    };

    connect();

    return () => {
      isUnmounted = true;

      if (reconnectTimeoutId !== null) {
        window.clearTimeout(reconnectTimeoutId);
      }

      if (socket) {
        console.log("[WebSocket] Cleaning up feature:", featureId);
        socket.onclose = null;
        try {
          socket.close();
        } catch (error) {
          console.error("[WebSocket] Cleanup failed:", error);
        }
      }
    };
  }, [selectedFeatureId, user, loadLayersFromBackend, items, itemsRef, commentRefs, dispatch]);

  return null;
}
