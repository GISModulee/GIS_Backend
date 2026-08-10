import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import toast from "react-hot-toast";
import { setFeatureHasComments } from "@/state/layersSlice.js";
import { buildCommentPopupHTML } from "@/utils/CommentPopupBuilder.js";
import { openCommentAttachment } from "@/utils/CommentAttachmentHandler.js";
import layerService from "@/utils/layerService.js";

export default function CommentGlobalsHandler({ user, itemsRef, commentRefs }) {
  const dispatch = useDispatch();
  const popupFilesRef = useRef({});
  const latestHandlersRef = useRef({});

  // Keep latest handlers up-to-date
  useEffect(() => {
    latestHandlersRef.current = { user, itemsRef, commentRefs };
  }, [user, itemsRef, commentRefs]);

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

        const toInt = (v) => { const n = parseInt(v, 10); return Number.isFinite(n) && n > 0 ? n : null; };
        let featureNumber = toInt(featureObj?.feature_number)
          || toInt(featureObj?.properties?.feature_no)
          || toInt(featureObj?.properties?.feature_number)
          || null;

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

    return () => {
      delete window.handlePopupFileChange;
      delete window.clearPopupFile;
      delete window.submitPopupComment;
      delete window.openCommentAttachment;
    };
  }, [dispatch]);

  return null;
}
