import { useEffect, useRef } from "react";
import { useMap as useLeafletMap } from "react-leaflet";
import { useDispatch } from "react-redux";
import layerService from "@/utils/layerService.js";
import { setFeatureHasComments } from "@/state/layersSlice.js";

export default function CommentSync({ items }) {
  const leafletMap = useLeafletMap();
  const dispatch = useDispatch();
  const checkedFeaturesRef = useRef(new Set());

  useEffect(() => {
    if (!leafletMap || !items || items.length === 0) return;

    let cancelled = false;

    const fetchMissingComments = async () => {
      const featuresNeeding = [];
      items.forEach((layer) => {
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
            checkedFeaturesRef.current.add(feature.backendId);
          }
        } catch (_) {
          // silently ignore per-feature errors
        }
      }
    };

    fetchMissingComments();
    return () => { cancelled = true; };
  }, [leafletMap, items, dispatch]);

  return null;
}
