import { useState } from "react";
import toast from "react-hot-toast";
import { useDispatch } from "react-redux";
import { openDeleteConfirm } from "@/state/layersSlice.js";
import {
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Check,
  X,
  Pencil,
  Maximize2,
  Trash2,
} from "lucide-react";
import { useLayers } from "@/hooks/useLayers.js";
import { useMap } from "@/hooks/useMap.js";
import LayerRenderer from "../layerRenderer/LayerRenderer.jsx";
import FeatureRow from "../featureRow/FeatureRow.jsx";

export default function LayerRow({ layer }) {
  const {
    renameLayer,
    removeLayer,
    toggleVisible,
    expandLayer,
    chooseLayer,
    selectedLayerId,
    dragFeature,
    items,
  } = useLayers();
  const { mapInstance } = useMap();

  const dispatch = useDispatch();
  const [editing, setEditing] = useState(false);
  const [nameVal, setNameVal] = useState(layer.name);
  const [dragOver, setDragOver] = useState(false);
  const [limit, setLimit] = useState(100);

  const isSelected = selectedLayerId === layer.localId;

  const handleRename = () => {
    const t = nameVal.trim();
    if (!t) return;
    if (!/^[a-zA-Z0-9\s]+$/.test(t)) {
      toast.error("Layer name must contain only letters, numbers, and spaces.");
      return;
    }
    if (t.length > 20) {
      toast.error("Layer name cannot exceed 20 characters.");
      return;
    }
    if (t !== layer.name) renameLayer(layer.localId, layer.backendId, t);
    setEditing(false);
  };

  const handleFlyToLayer = () => {
    LayerRenderer.flyToLayer(layer.localId, items, mapInstance);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const featureLocalId = e.dataTransfer.getData("featureLocalId");
    const fromLayerLocalId = e.dataTransfer.getData("fromLayerLocalId");
    const featureBackendId = e.dataTransfer.getData("featureBackendId");
    const toLayerBackendId = layer.backendId;
    if (featureLocalId && fromLayerLocalId !== layer.localId) {
      dragFeature(
        featureLocalId,
        fromLayerLocalId,
        layer.localId,
        featureBackendId,
        toLayerBackendId,
      );
    }
  };

  return (
    <div
      className={`rounded-xl border transition-all
        ${isSelected ? "border-blue-300 dark:border-blue-700 bg-blue-50/60 dark:bg-blue-900/30" : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"}
        ${dragOver ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/50 shadow-md" : ""}
        ${layer.status === "error" ? "border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      {/* Layer header row */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer"
        onClick={() => chooseLayer(isSelected ? null : layer.localId)}
      >
        {/* Expand arrow */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            expandLayer(layer.localId);
          }}
          className="p-0.5 text-gray-400 hover:text-gray-600 flex-shrink-0"
        >
          {layer.expanded ? (
            <ChevronDown size={13} />
          ) : (
            <ChevronRight size={13} />
          )}
        </button>

        {/* Eye */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleVisible(layer.localId, layer.backendId, layer.visible);
          }}
          className="text-gray-400 hover:text-blue-500 flex-shrink-0"
        >
          {layer.visible ? (
            <Eye size={14} />
          ) : (
            <EyeOff size={14} className="text-gray-300 dark:text-gray-600" />
          )}
        </button>

        {/* Name */}
        {editing ? (
          <input
            autoFocus
            value={nameVal}
            onChange={(e) => {
              const val = e.target.value;
              if (/^[a-zA-Z0-9\s]*$/.test(val) && val.length <= 20) {
                setNameVal(val);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setEditing(false);
            }}
            onClick={(e) => e.stopPropagation()}
            className="flex-1 text-xs border border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-white rounded px-1 py-0.5 outline-none min-w-0"
          />
        ) : (
          <span 
            className="flex-1 text-xs font-semibold text-gray-700 dark:text-gray-200 truncate min-w-0"
            title={layer.name}
          >
            {layer.name}
          </span>
        )}

        {/* Feature count badge */}
        {layer.features.length > 0 && (
          <span className="text-[10px] bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-300 rounded-full px-1.5 py-0.5 flex-shrink-0">
            {layer.features.length}
          </span>
        )}

        {/* Action buttons */}
        <div
          className="flex items-center gap-0.5 flex-shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          {editing ? (
            <>
              <button
                onClick={handleRename}
                className="p-1 hover:text-green-600 rounded"
              >
                <Check size={12} />
              </button>
              <button
                onClick={() => setEditing(false)}
                className="p-1 hover:text-gray-400 rounded"
              >
                <X size={12} />
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => {
                  setEditing(true);
                  setNameVal(layer.name);
                }}
                className="p-1 hover:text-blue-500 rounded text-gray-400"
              >
                <Pencil size={12} />
              </button>
              <button
                onClick={handleFlyToLayer}
                className="p-1 hover:text-blue-500 rounded text-gray-400"
              >
                <Maximize2 size={12} />
              </button>
              <button
                onClick={() =>
                  dispatch(
                    openDeleteConfirm({
                      type: "layer",
                      targetId: layer.localId,
                      backendId: layer.backendId,
                      name: layer.name,
                      featuresList: layer.features,
                    })
                  )
                }
                className="p-1 hover:text-red-500 rounded text-gray-400"
              >
                <Trash2 size={12} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Features list */}
      {layer.expanded && layer.features.length > 0 && (
        <div className="pb-1 border-t border-gray-100 dark:border-gray-800">
          {layer.features.slice(0, limit).map((feature) => (
            <FeatureRow key={feature.localId} feature={feature} layer={layer} />
          ))}
          {layer.features.length > limit && (
            <div className="flex flex-col items-center gap-1 py-2 border-t border-gray-50 dark:border-gray-800/50">
              <span className="text-[10px] text-gray-400 dark:text-gray-500">
                Showing {limit} of {layer.features.length} features.
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setLimit((prev) => prev + 200);
                }}
                className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline"
              >
                Show More
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty drop hint */}
      {layer.expanded && layer.features.length === 0 && (
        <div className="pb-2 px-7 text-[11px] text-gray-300 dark:text-gray-600 border-t border-gray-100 dark:border-gray-800 pt-1.5">
          No features — drag one here
        </div>
      )}
    </div>
  );
}
