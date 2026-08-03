import { useState } from "react";
import { useSelector } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import toast from "react-hot-toast";
import FeatureSelector from "../featureSelector/FeatureSelector.jsx";

export default function UnionAction({ onCancel }) {
  const [selectedFeatures, setSelectedFeatures] = useState([]);
  const [resultName, setResultName] = useState("");
  const [loading, setLoading] = useState(false);

  const { items, loadLayersFromBackend } = useLayers();

  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const handleRun = async () => {
    if (!Array.isArray(selectedFeatures) || selectedFeatures.length < 2) {
      toast.error("Please select at least 2 features to perform Union.");
      return;
    }

    const selectedObjs = [];
    items.forEach((lyr) => {
      (lyr.features || []).forEach((f) => {
        if (selectedFeatures.includes(f.localId)) {
          selectedObjs.push(f);
        }
      });
    });

    if (selectedObjs.length < 2) {
      toast.error("Could not find the selected features.");
      return;
    }

    setLoading(true);
    const toastId = toast.loading("Computing and saving union layer...");
    try {
      const defaultName = `Union (${selectedObjs.map(f => f.name || "Feature").join(" & ")})`;
      const name = resultName.trim() || defaultName;

      const response = await layerService.runUnion({
        case_id: activeCaseId,
        feature_numbers: selectedObjs.map(f => f.feature_number),
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
        color: "#6366f1",
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
        properties: { name, color: "#6366f1" },
      });

      // Reload layers from backend to render the new layer and feature
      await loadLayersFromBackend();

      toast.success(saveRes?.message || response?.message || newLayer?.message || "✓ Union layer created and added to map!", { id: toastId });
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
          Union Settings
        </span>
        <button
          onClick={onCancel}
          disabled={loading}
          className="text-[9px] text-blue-600 dark:text-blue-400 hover:underline"
        >
          Cancel
        </button>
      </div>

      <div>
        <FeatureSelector
          label="Select Features"
          value={selectedFeatures}
          onChange={setSelectedFeatures}
          items={items}
          disabled={loading}
          multiple={true}
          placeholder="— select multiple features —"
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
          placeholder="Union result"
          disabled={loading}
          className="w-full px-1.5 py-0.5 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded text-[11px] text-gray-800 dark:text-gray-200 focus:outline-none focus:border-blue-500"
        />
      </div>

      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full py-1 bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-medium rounded shadow transition-colors disabled:opacity-50"
      >
        {loading ? "Saving..." : "Run Union"}
      </button>
    </div>
  );
}
