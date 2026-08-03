import { useState } from "react";
import { useSelector } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import toast from "react-hot-toast";
import FeatureSelector from "../featureSelector/FeatureSelector.jsx";
import { doFeaturesIntersect } from "@/utils/vectorOps.js";

export default function IntersectionAction({ onCancel }) {
  const [featureA, setFeatureA] = useState("");
  const [featureB, setFeatureB] = useState("");
  const [resultName, setResultName] = useState("");
  const [loading, setLoading] = useState(false);

  const { items, loadLayersFromBackend } = useLayers();

  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const handleRun = async () => {
    if (!featureA || !featureB) {
      toast.error("Please select both Feature A and Feature B.");
      return;
    }

    if (featureA === featureB) {
      toast.error("Select two different features.");
      return;
    }

    let featAObj = null;
    let featBObj = null;

    items.forEach((lyr) => {
      const foundA = lyr.features?.find((f) => f.localId === featureA);
      if (foundA) featAObj = foundA;
      const foundB = lyr.features?.find((f) => f.localId === featureB);
      if (foundB) featBObj = foundB;
    });

    if (!featAObj || !featBObj) {
      toast.error("Could not find the selected features.");
      return;
    }

    // Check if features intersect (removed client-side check as requested, handled by backend)

    setLoading(true);
    const toastId = toast.loading("Computing and saving intersection layer...");
    try {
      const nameA = featAObj.name || "A";
      const nameB = featBObj.name || "B";
      const name = resultName.trim() || `Intersection (${nameA} & ${nameB})`;

      const response = await layerService.runIntersection({
        case_id: activeCaseId,
        feature_numbers: [featAObj.feature_number, featBObj.feature_number],
      });

      const feat = response?.features ? response.features[0] : response;
      let geom = feat?.geometry || feat;

      if (typeof geom === "string") {
        try {
          geom = JSON.parse(geom);
        } catch (_) { }
      }

      if (!geom) {
        toast.error("No result geometry returned from backend.", { id: toastId });
        setLoading(false);
        return;
      }

      // 1. Create a separate layer on the backend
      const newLayer = await layerService.createLayer({
        case_id: activeCaseId,
        name: name,
        layer_type: "auto",
        visible: true,
        opacity: 1,
        color: "#10b981",
      });

      const layerId = newLayer?.id ?? newLayer?.layer_id;

      if (!newLayer || layerId === undefined || layerId === null) {
        throw new Error(`Failed to create result layer: ${JSON.stringify(newLayer)}`);
      }

      // 2. Save the computed feature to this newly created layer
      const saveRes = await layerService.createFeature({
        name,
        layer_id: layerId,
        case_id: activeCaseId,
        created_by: 1,
        geometry: geom,
        geometry_type: geom.type || "Polygon",
        properties: { name, color: "#10b981" },
      });

      // Reload layers from backend to render the new layer and feature
      await loadLayersFromBackend();

      toast.success(saveRes?.message || response?.message || newLayer?.message || "✓ Intersection layer created and added to map!", { id: toastId });
      if (onCancel) onCancel();
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.message || e.response?.data?.detail || e.message || "Operation failed", { id: toastId });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2 pt-1 border-t border-gray-100 dark:border-gray-800">
      <div className="flex justify-between items-center px-0.5">
        <span className="text-[11px] font-bold text-gray-700 dark:text-gray-300">
          Intersection Settings
        </span>
        <button
          onClick={onCancel}
          disabled={loading}
          className="text-[9px] text-blue-600 dark:text-blue-400 hover:underline"
        >
          Cancel
        </button>
      </div>

      <div className="grid grid-cols-2 gap-1.5">
        <FeatureSelector
          label="Feature A"
          value={featureA}
          onChange={setFeatureA}
          items={items}
          disabled={loading}
        />
        <FeatureSelector
          label="Feature B"
          value={featureB}
          onChange={setFeatureB}
          items={items}
          disabled={loading}
        />
      </div>

      <div>
        <label className="block text-[9px] font-semibold text-gray-500 dark:text-gray-400 mb-0.5">
          Result name (optional)
        </label>
        <input
          type="text"
          value={resultName}
          onChange={(e) => setResultName(e.target.value)}
          placeholder="Intersection result"
          disabled={loading}
          className="w-full px-1.5 py-0.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded text-[11px] text-gray-800 dark:text-gray-200 focus:outline-none focus:border-blue-500"
        />
      </div>

      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full py-1 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-medium rounded shadow transition-colors disabled:opacity-50"
      >
        {loading ? "Saving..." : "Run Intersection"}
      </button>
    </div>
  );
}
