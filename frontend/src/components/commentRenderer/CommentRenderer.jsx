import { useEffect, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import toast from "react-hot-toast";
import { selectFeature } from "@/state/layersSlice.js";
import { buildCommentPopupHTML } from "@/utils/CommentPopupBuilder.js";
import { openCommentAttachment } from "@/utils/CommentAttachmentHandler.js";
import { API_URLS } from "@/config/apiConfig.js";

const commentBubbleIcon = L.divIcon({
  html: `
    <div style="
      width: 26px; height: 26px;
      background: #3b82f6;
      border: 2.5px solid #ffffff;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0px 2.5px 6px rgba(0,0,0,0.35);
      cursor: pointer;
    ">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
    </div>
  `,
  className: 'custom-comment-bubble',
  iconSize: [26, 26],
  iconAnchor: [13, 13],
});


export default function CommentRenderer({ commentRefs, itemsRef }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const { items, loadLayersFromBackend } = useLayers();
  const user = useSelector((s) => s.auth.user);
  const popupFilesRef = useRef({});
  const selectedFeatureId = useSelector(
    (state) => state.layers.selectedFeatureId
  );

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
        console.error(
          "[WebSocket] Access token is missing."
        );
        return;
      }

      /*
       * Works whether API_URLS.LAYERS is:
       * http://192.168.8.29:8000/layers
       * or a relative URL such as /layers.
       */
      const websocketUrl = new URL(
        API_URLS.LAYERS,
        window.location.origin
      );

      websocketUrl.protocol =
        websocketUrl.protocol === "https:"
          ? "wss:"
          : "ws:";

      // Replace the API path instead of appending to /layers.
      websocketUrl.pathname =
        `/ws/cases/${caseId}/features/${featureNumber}/comments`;

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

          console.log(
            "[WebSocket] Received:",
            message
          );

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

          // Automatically get the updated server state.
          const rawComments =
            await layerService.getComments(caseId, featureNumber);

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

          /*
           * Update the currently open popup immediately.
           * No close, reopen, or browser refresh is required.
           */
          if (marker?.isPopupOpen()) {
            marker.setPopupContent(
              buildCommentPopupHTML(
                updatedCommentsList,
                featureId,
                user
              )
            );
          }

          /*
           * Synchronize Redux/layer state if this function is
           * responsible for storing comment counts or feature data.
           */
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

        // Authentication errors require a new login/token.
        if (event.code === 1008) {
          console.error(
            "[WebSocket] Authentication failed. " +
            "Connection will not reconnect."
          );
          return;
        }

        const delay = reconnectDelay;

        console.log(
          `[WebSocket] Reconnecting in ${delay}ms...`
        );

        reconnectTimeoutId = window.setTimeout(
          connect,
          delay
        );

        reconnectDelay = Math.min(
          reconnectDelay * 2,
          16000
        );
      };

      socket.onerror = (error) => {
        console.error(
          "[WebSocket] Connection error:",
          error
        );

        /*
         * onclose performs the reconnect.
         */
        try {
          socket.close();
        } catch (closeError) {
          console.error(
            "[WebSocket] Failed to close socket:",
            closeError
          );
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
        console.log(
          "[WebSocket] Cleaning up feature:",
          featureId
        );

        socket.onclose = null;

        try {
          socket.close();
        } catch (error) {
          console.error(
            "[WebSocket] Cleanup failed:",
            error
          );
        }
      }
    };
  }, [
    selectedFeatureId,
    user,
    loadLayersFromBackend,
  ]);

  useEffect(() => {
    window.handlePopupFileChange = (featureBackendId, inputEl) => {
      const file = inputEl.files[0];
      if (file) {
        popupFilesRef.current[featureBackendId] = file;
        const nameEl = document.getElementById(`popup-file-name-${featureBackendId}`);
        if (nameEl) {
          nameEl.textContent = `📎 ${file.name}`;
        }
        const previewEl = document.getElementById(`popup-file-preview-${featureBackendId}`);
        if (previewEl) {
          previewEl.style.display = "flex";
        }
      }
    };

    window.clearPopupFile = (featureBackendId) => {
      delete popupFilesRef.current[featureBackendId];
      const inputEl = document.getElementById(`popup-file-input-${featureBackendId}`);
      if (inputEl) inputEl.value = "";
      const nameEl = document.getElementById(`popup-file-name-${featureBackendId}`);
      if (nameEl) {
        nameEl.textContent = "📎 File selected";
      }
      const previewEl = document.getElementById(`popup-file-preview-${featureBackendId}`);
      if (previewEl) previewEl.style.display = "none";
    };

    window.openCommentAttachment = openCommentAttachment;

    window.submitPopupComment = async (featureBackendId) => {
      if (!featureBackendId || featureBackendId === "undefined" || featureBackendId === "null" || isNaN(Number(featureBackendId))) {
        toast.error("Cannot add comment: Feature has no valid ID.");
        return;
      }

      const inputEl = document.getElementById(`popup-comment-input-${featureBackendId}`);
      const commentText = inputEl ? inputEl.value.trim() : "";
      const file = popupFilesRef.current[featureBackendId] || null;

      if (!commentText && !file) {
        toast.error("Please enter a comment or attach an image");
        return;
      }

      const toastId = toast.loading("Saving comment...");

      try {
        const allFeatures = itemsRef.current.flatMap((layer) => layer.features || []);
        const featureObj = allFeatures.find(
          (f) => Number(f.backendId) === Number(featureBackendId) || String(f.backendId) === String(featureBackendId)
        );
        const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
        const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : null;
        const caseId = featureObj?.case_id || featureObj?.properties?.case_id || resolvedCaseId;
        const featureNumber = featureObj?.feature_number || featureObj?.properties?.feature_no || featureObj?.properties?.feature_number;

        if (!caseId || !featureNumber) {
          throw new Error(`Could not find caseId (${caseId}) or featureNumber (${featureNumber}) for this feature.`);
        }

        const res = await layerService.addComment(caseId, featureNumber, commentText, file);

        if (inputEl) inputEl.value = "";
        window.clearPopupFile(featureBackendId);

        const rawComments = await layerService.getComments(caseId, featureNumber);
        const updatedCommentsList = await Promise.all(
          rawComments.map(async (c) => {
            let imgSrc = null;
            if (c.has_attachment || c.has_image || c.image_id || c.image || c.attachment) {
              try {
                imgSrc = await layerService.getCommentImage(c.id);
              } catch (_) { }
            }
            return { ...c, imgSrc };
          })
        );

        toast.success(res?.message || res?.detail || "Comment added!", { id: toastId });

        const localId = itemsRef.current
          .flatMap(lyr => lyr.features || [])
          .find(feat => feat.backendId === Number(featureBackendId) || feat.id === Number(featureBackendId))
          ?.localId;

        const marker = localId ? commentRefs.current[localId] : null;
        if (marker) {
          setTimeout(() => {
            try {
              marker.setPopupContent(buildCommentPopupHTML(updatedCommentsList, featureBackendId, user));
              marker.openPopup();
            } catch (popupErr) {
              console.error("Error setting popup content:", popupErr);
            }
          }, 50);
        }
      } catch (err) {
        console.error("[submitPopupComment] Failed to submit popup comment:", err);
        const errMsg = err.response?.data?.detail || err.response?.data?.message || err.message || "Failed to add comment";
        toast.error(`Error: ${errMsg}`, { id: toastId });
      }
    };

    return () => {
      delete window.handlePopupFileChange;
      delete window.clearPopupFile;
      delete window.submitPopupComment;
      delete window.openCommentAttachment;
    };
  }, [user, itemsRef, commentRefs, loadLayersFromBackend]);

  useEffect(() => {
    if (!leafletMap) return;

    const allFeatureIds = new Set();
    items.forEach((layer) => layer.features.forEach((f) => allFeatureIds.add(f.localId)));

    Object.keys(commentRefs.current).forEach((id) => {
      if (!allFeatureIds.has(id)) {
        try { leafletMap.removeLayer(commentRefs.current[id]); } catch (_) { }
        delete commentRefs.current[id];
      }
    });

    items.forEach((layer) => {
      layer.features.forEach((feature) => {
        const shouldShow = layer.visible && feature.visible;
        const existingMarker = commentRefs.current[feature.localId];

        if (shouldShow && feature.commentsList && feature.commentsList.length > 0) {
          let centerLatLng = null;
          if (feature.geometry?.type === "Point") {
            const coords = feature.geometry.coordinates;
            centerLatLng = L.latLng(coords[1], coords[0]);
          } else if (feature.geometry) {
            try {
              const tempGeoJSON = L.geoJSON({ type: "Feature", geometry: feature.geometry });
              centerLatLng = tempGeoJSON.getBounds().getCenter();
            } catch (_) { }
          }

          if (centerLatLng) {
            if (existingMarker) {
              existingMarker.setLatLng(centerLatLng);
              if (!existingMarker.isPopupOpen()) {
                existingMarker.setPopupContent(buildCommentPopupHTML(feature.commentsList, feature.backendId || feature.id, user));
              }
            } else {
              const commentMarker = L.marker(centerLatLng, {
                icon: commentBubbleIcon,
                zIndexOffset: 1000
              }).addTo(leafletMap);

              commentMarker.bindPopup(buildCommentPopupHTML(feature.commentsList, feature.backendId || feature.id, user), {
                className: "comment-popup"
              });

              commentMarker.on("popupopen", async () => {
                const featId = feature.backendId || feature.id;
                if (!featId) return;
                commentMarker.setPopupContent(buildCommentPopupHTML([], featId, user, true));
                dispatch(selectFeature(featId));
                try {
                  const caseId = feature.case_id;
                  const featureNumber = feature.feature_number;
                  if (!caseId || !featureNumber) return;
                  const rawComments = await layerService.getComments(caseId, featureNumber);
                  const updatedCommentsList = await Promise.all(
                    rawComments.map(async (c) => {
                      let imgSrc = null;
                      if (c.has_attachment || c.has_image || c.image_id || c.image || c.attachment) {
                        try {
                          imgSrc = await layerService.getCommentImage(c.id);
                        } catch (_) { }
                      }
                      return { ...c, imgSrc };
                    })
                  );
                  commentMarker.setPopupContent(buildCommentPopupHTML(updatedCommentsList, featId, user, false));
                } catch (err) {
                  console.error("Failed to fetch comments on popup open:", err);
                  commentMarker.setPopupContent(buildCommentPopupHTML([], featId, user, false));
                }
              });

              commentMarker.on("popupclose", () => {
                const featId = feature.backendId || feature.id;
                if (featId) {
                  window.clearPopupFile(featId);
                }
              });

              commentRefs.current[feature.localId] = commentMarker;
            }
          }
        } else {
          if (existingMarker) {
            try { leafletMap.removeLayer(existingMarker); } catch (_) { }
            delete commentRefs.current[feature.localId];
          }
        }
      });
    });
  }, [items, leafletMap, commentRefs, user]);

  return null;
}

