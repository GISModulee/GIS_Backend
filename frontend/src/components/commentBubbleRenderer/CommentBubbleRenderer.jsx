import { useEffect } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useDispatch } from "react-redux";
import L from "leaflet";
import { selectFeature, setFeatureHasComments } from "@/state/layersSlice.js";
import { buildCommentPopupHTML } from "@/utils/CommentPopupBuilder.js";
import layerService from "@/utils/layerService.js";

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

export default function CommentBubbleRenderer({ commentRefs, itemsRef, items, user }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();

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
      const isGeoclipOrImageLayer =
        layer.type === 'geoclip' ||
        (layer.name && /\.(png|jpe?g|gif|webp|tiff?|bmp)$/i.test(layer.name));
      if (isGeoclipOrImageLayer) return;

      layer.features.forEach((feature) => {
        const shouldShow = layer.visible && feature.visible;
        const existingMarker = commentRefs.current[feature.localId];

        const hasComments = (feature.commentsList && feature.commentsList.length > 0) || feature.hasComments || feature.comments_count > 0;
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
                if (featId && window.clearPopupFile) {
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
  }, [items, leafletMap, commentRefs, user, itemsRef, dispatch]);

  return null;
}
