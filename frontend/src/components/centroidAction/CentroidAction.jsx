import { useState } from "react";
import { useSelector } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import toast from "react-hot-toast";
import FeatureSelector from "../featureSelector/FeatureSelector.jsx";

export default function CentroidAction({ onCancel }) {
  const [featureA, setFeatureA] = useState("");
  const [resultName, setResultName] = useState("");
  const [loading, setLoading] = useState(false);

  const { items, loadLayersFromBackend } = useLayers();

  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const handleRun = async () => {
    if (!featureA) {
      toast.error("Please select a feature.");
      return;
    }

    let featAObj = null;
    items.forEach((lyr) => {
      const foundA = lyr.features?.find((f) => f.localId === featureA);
      if (foundA) featAObj = foundA;
    });

    if (!featAObj) {
      toast.error("Could not find selected feature.");
      return;
    }

    setLoading(true);
    const toastId = toast.loading("Computing centroid...");
    try {
      const response = await layerService.runCentroid({
        case_id: activeCaseId,
        feature_number: featAObj.feature_number,
        layer_name: resultName.trim() || undefined,
        name: resultName.trim() || undefined,
      });

      // Backend creates the layer automatically — just reload to reflect it
      await loadLayersFromBackend();

      toast.success(response?.message || "✓ Centroid layer created and added to map!", { id: toastId });
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
          Centroid Settings
        </span>
        <button
          onClick={onCancel}
          disabled={loading}
          className="text-[9px] text-blue-600 dark:text-blue-400 hover:underline"
        >
          Cancel
        </button>
      </div>

      <FeatureSelector
        label="Input Feature"
        value={featureA}
        onChange={setFeatureA}
        items={items}
        placeholder="— select feature —"
        disabled={loading}
      />

      <div>
        <label className="block text-[9px] font-semibold text-gray-500 dark:text-gray-400 mb-0.5">
          Result name (optional)
        </label>
        <input
          type="text"
          value={resultName}
          onChange={(e) => setResultName(e.target.value)}
          placeholder="Centroid result"
          disabled={loading}
          className="w-full px-1.5 py-0.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded text-[11px] text-gray-800 dark:text-gray-200 focus:outline-none focus:border-blue-500"
        />
      </div>

      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full py-1 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-medium rounded shadow transition-colors disabled:opacity-50"
      >
        {loading ? "Saving..." : "Run Centroid"}
      </button>
    </div>
  );
}
