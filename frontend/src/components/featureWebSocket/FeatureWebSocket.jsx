// src/components/featureWebSocket/FeatureWebSocket.jsx
import { useFeatureWebSocket } from "@/hooks/useFeatureWebSocket.js";

export default function FeatureWebSocket({ caseId }) {
  useFeatureWebSocket({ caseId });
  return null;
}
