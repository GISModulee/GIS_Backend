import { useEffect, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useSelector, useDispatch } from "react-redux";
import L from "leaflet";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import toast from "react-hot-toast";
import { selectFeature, setFeatureHasComments } from "@/state/layersSlice.js";
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
  const checkedFeaturesRef = useRef(new Set());
  // Stable ref that always holds the latest handler closures.
  // window globals delegate through this so they never become stale.
  const latestHandlersRef = useRef({});
  const userRef = useRef(user);
  const selectedFeatureId = useSelector(
    (state) => state.layers.selectedFeatureId
  );

  // Keep latestHandlersRef up-to-date on every render without re-registering window globals.
  latestHandlersRef.current = { user, itemsRef, commentRefs, loadLayersFromBackend };

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

  // Register window globals ONCE at mount. Each function delegates to latestHandlersRef
  // so they always use the latest closure values without ever being re-registered.
  useEffect(() => {
    window.handlePopupFileChange = (featureBackendId, inputEl) => {
      const file = inputEl.files[0];
      if (file) {
        popupFilesRef.current[featureBackendId] = file;
        const nameEl = document.getElementById(`popup-file-name-${featureBackendId}`);
        if (nameEl) nameEl.textContent = `📎 ${file.name}`;
        const previewEl = document.getElementById(`popup-file-preview-${featureBackendId}`);
        if (previewEl) previewEl.style.display = "flex";
      }
    };

    window.clearPopupFile = (featureBackendId) => {
      delete popupFilesRef.current[featureBackendId];
      const inputEl = document.getElementById(`popup-file-input-${featureBackendId}`);
      if (inputEl) inputEl.value = "";
      const nameEl = document.getElementById(`popup-file-name-${featureBackendId}`);
      if (nameEl) nameEl.textContent = "📎 File selected";
      const previewEl = document.getElementById(`popup-file-preview-${featureBackendId}`);
      if (previewEl) previewEl.style.display = "none";
    };

    window.openCommentAttachment = openCommentAttachment;

    window.submitPopupComment = async (featureBackendId) => {
      // Always read the latest values from the ref — never stale
      const { user: currentUser, itemsRef: currentItemsRef, commentRefs: currentCommentRefs } = latestHandlersRef.current;

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
        const allFeatures = currentItemsRef.current.flatMap((layer) => layer.features || []);
        const featureObj = allFeatures.find(
          (f) => Number(f.backendId) === Number(featureBackendId) || String(f.backendId) === String(featureBackendId)
        );
        const owningLayer = featureObj
          ? currentItemsRef.current.find((l) => l.localId === featureObj.layerLocalId)
          : null;

        const currentMatch = window.location.pathname.match(/\/map\/(\d+)/);
        const resolvedCaseId = currentMatch ? parseInt(currentMatch[1], 10) : null;
        const caseId = featureObj?.case_id || featureObj?.properties?.case_id || resolvedCaseId;
        const layerId = owningLayer?.backendId || featureObj?.layer_id;

        // Resolve feature_number — only accept valid positive integers
        const toInt = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) && n > 0 ? n : null; };
        let featureNumber = toInt(featureObj?.feature_number)
          || toInt(featureObj?.properties?.feature_no)
          || toInt(featureObj?.properties?.feature_number)
          || null;

        // If still not resolved or to verify, fetch live from the layer features endpoint first
        if (caseId && layerId && featureBackendId) {
          try {
            const layerFeatures = await layerService.getFeaturesByLayer(caseId, layerId);
            const match = Array.isArray(layerFeatures)
              ? layerFeatures.find((lf) => Number(lf.id) === Number(featureBackendId))
              : null;
            const resolvedNum = toInt(match?.feature_number) || toInt(match?.id) || featureNumber;
            if (resolvedNum) {
              featureNumber = resolvedNum;
              try {
                const singleFeat = await layerService.getSingleFeature(caseId, layerId, featureNumber);
                if (singleFeat) {
                  const singleNum = toInt(singleFeat.feature_number) || toInt(singleFeat.id);
                  if (singleNum) featureNumber = singleNum;
                }
              } catch (_) { }
            }
          } catch (lookupErr) {
            console.warn("[submitPopupComment] feature lookup failed:", lookupErr);
          }
        }

        if (!caseId || !layerId || !featureNumber) {
          throw new Error(`Could not resolve caseId (${caseId}), layerId (${layerId}), or featureNumber (${featureNumber}) for this feature.`);
        }

        const res = await layerService.addComment(caseId, layerId, featureNumber, commentText, file);

        if (inputEl) inputEl.value = "";
        window.clearPopupFile(featureBackendId);

        await layerService.getComments(caseId, layerId, featureNumber);
        const rawComments = await layerService.getCommentsThread(caseId, layerId, featureNumber);
        const updatedCommentsList = await Promise.all(
          rawComments.map(async (c) => {
            let imgSrc = null;
            if (c.has_attachment || c.has_image || c.image_id || c.image || c.attachment) {
              try {
                imgSrc = await layerService.getCommentImage(caseId, layerId, featureNumber, c.id);
              } catch (_) { }
            }
            return { ...c, imgSrc };
          })
        );

        dispatch(setFeatureHasComments({ backendId: featureBackendId, hasComments: true, commentsList: updatedCommentsList }));

        toast.success(res?.message || res?.detail || "Comment added!", { id: toastId });

        const localId = currentItemsRef.current
          .flatMap(lyr => lyr.features || [])
          .find(feat => feat.backendId === Number(featureBackendId) || feat.id === Number(featureBackendId))
          ?.localId;

        const marker = localId ? currentCommentRefs.current[localId] : null;
        if (marker) {
          setTimeout(() => {
            try {
              marker.setPopupContent(buildCommentPopupHTML(updatedCommentsList, featureBackendId, currentUser));
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

    // Cleanup only on unmount — never in between renders
    return () => {
      delete window.handlePopupFileChange;
      delete window.clearPopupFile;
      delete window.submitPopupComment;
      delete window.openCommentAttachment;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount/unmount only

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
      // Skip geoclip/image layers — they don't support comments
      const isGeoclipOrImageLayer =
        layer.type === 'geoclip' ||
        (layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name));
      if (isGeoclipOrImageLayer) return;

      layer.features.forEach((feature) => {
        const shouldShow = layer.visible && feature.visible;
        const existingMarker = commentRefs.current[feature.localId];

        // Only show comment bubble icon for features that have comments
        const hasComments = (feature.commentsList && feature.commentsList.length > 0) || feature.hasComments || feature.comments_count > 0;
        // Remove existing marker if it no longer has comments and the popup is not open
        if (existingMarker && !hasComments && !existingMarker.isPopupOpen()) {
          try { leafletMap.removeLayer(existingMarker); } catch (_) { }
          delete commentRefs.current[feature.localId];
        }
        if (shouldShow && feature.backendId && hasComments) {
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
                  // Always resolve fresh from Redux state to get up-to-date layer_id / feature_number
                  const freshFeature = itemsRef.current
                    .flatMap((l) => l.features || [])
                    .find((f) => f.backendId === featId || f.localId === String(featId));
                  const freshLayer = freshFeature
                    ? itemsRef.current.find((l) => l.localId === freshFeature.layerLocalId)
                    : null;

                  const caseId = freshFeature?.case_id || feature.case_id;
                  const layerId = freshLayer?.backendId || freshFeature?.layer_id || feature.layer_id;
                  const featureNumber = (freshFeature?.feature_number && Number.isInteger(Number(freshFeature.feature_number)))
                    ? freshFeature.feature_number
                    : (feature.feature_number && Number.isInteger(Number(feature.feature_number)))
                      ? feature.feature_number
                      : null;

                  if (!caseId || !layerId || !featureNumber) {
                    console.warn("[popupopen] Missing caseId/layerId/featureNumber", { caseId, layerId, featureNumber });
                    return;
                  }

                  await layerService.getComments(caseId, layerId, featureNumber);
                  const rawComments = await layerService.getCommentsThread(caseId, layerId, featureNumber);
                  const updatedCommentsList = await Promise.all(
                    rawComments.map(async (c) => {
                      let imgSrc = null;
                      if (c.has_attachment || c.has_image || c.image_id || c.image || c.attachment) {
                        try {
                          imgSrc = await layerService.getCommentImage(caseId, layerId, featureNumber, c.id);
                        } catch (_) { }
                      }
                      return { ...c, imgSrc };
                    })
                  );
                  commentMarker.setPopupContent(buildCommentPopupHTML(updatedCommentsList, featId, user, false));
                  dispatch(setFeatureHasComments({
                    backendId: featId,
                    hasComments: updatedCommentsList.length > 0,
                    commentsList: updatedCommentsList,
                    commentsCount: updatedCommentsList.length
                  }));
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
          if (existingMarker && !existingMarker.isPopupOpen()) {
            try { leafletMap.removeLayer(existingMarker); } catch (_) { }
            delete commentRefs.current[feature.localId];
          }
        }
      });
    });
  }, [items, leafletMap, commentRefs, user]);


  // After initial load, fetch comment data for features that don't yet have hasComments set.
  // This ensures comment icons appear after a page refresh even when the layer API
  // doesn't return comment counts.
  useEffect(() => {
    if (!leafletMap || !items || items.length === 0) return;

    let cancelled = false;

    const fetchMissingComments = async () => {
      const featuresNeeding = [];
      items.forEach((layer) => {
        // Skip geoclip/image layers — they don't support the standard comments endpoint
        const isGeoclipOrImageLayer =
          layer.type === 'geoclip' ||
          (layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name));
        if (isGeoclipOrImageLayer) return;

        (layer.features || []).forEach((f) => {
          const hasComments = f.hasComments || f.comments_count > 0 || (f.commentsList && f.commentsList.length > 0);
          if (hasComments && f.backendId) {
            checkedFeaturesRef.current.delete(f.backendId);
            checkedFeaturesRef.current.delete(Number(f.backendId));
            return;
          }

          if (
            f.backendId &&
            f.case_id &&
            f.layer_id &&
            f.feature_number &&
            !hasComments &&
            !checkedFeaturesRef.current.has(f.backendId)
          ) {
            featuresNeeding.push(f);
          }
        });
      });

      for (const feature of featuresNeeding) {
        if (cancelled) break;
        try {
          const comments = await layerService.getComments(
            feature.case_id,
            feature.layer_id,
            feature.feature_number
          );
          if (!cancelled && comments && comments.length > 0) {
            dispatch(
              setFeatureHasComments({
                backendId: feature.backendId,
                hasComments: true,
                commentsList: comments,
                commentsCount: comments.length,
              })
            );
          } else {
            // Only mark as checked if it has 0 comments, so we don't query it again.
            // Features with comments will not be queried anyway because hasComments becomes true.
            checkedFeaturesRef.current.add(feature.backendId);
          }
        } catch (_) {
          // silently ignore per-feature errors
        }
      }
    };

    fetchMissingComments();
    return () => { cancelled = true; };
    // Re-run whenever the items array identity changes (i.e. after any loadLayersFromBackend call),
    // which resets hasComments on all features and requires us to re-fetch comment counts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leafletMap, items]);

  return null;

}

