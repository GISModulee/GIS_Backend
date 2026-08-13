import { useSelector } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import CommentGlobalsHandler from "../commentGlobalsHandler/CommentGlobalsHandler.jsx";
import CommentWebSocket from "../commentWebSocket/CommentWebSocket.jsx";
import CommentBubbleRenderer from "../commentBubbleRenderer/CommentBubbleRenderer.jsx";

export default function CommentRenderer({ commentRefs, itemsRef }) {
  const { items, loadLayersFromBackend } = useLayers();
  const user = useSelector((s) => s.auth.user);
  const selectedFeatureId = useSelector(
    (state) => state.layers.selectedFeatureId
  );

  return (
    <>
      <CommentGlobalsHandler 
        user={user} 
        itemsRef={itemsRef} 
        commentRefs={commentRefs} 
      />
      <CommentWebSocket 
        selectedFeatureId={selectedFeatureId}
        items={items}
        itemsRef={itemsRef}
        commentRefs={commentRefs}
        user={user}
        loadLayersFromBackend={loadLayersFromBackend}
      />
      <CommentBubbleRenderer 
        commentRefs={commentRefs}
        itemsRef={itemsRef}
        items={items}
        user={user}
      />
    </>
  );
}
