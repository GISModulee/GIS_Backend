import { useState } from "react";
import toast from "react-hot-toast";
import {
  Eye,
  EyeOff,
  Check,
  X,
  GripVertical,
  Pencil,
  Trash2,
  Maximize2,
} from "lucide-react";
import { useLayers } from "@/hooks/useLayers.js";
import { useMap } from "@/hooks/useMap.js";
import LayerRenderer from "../layerRenderer/LayerRenderer.jsx";
import { useDispatch } from "react-redux";
import { setHoveredFeatureId } from "@/state/layersSlice.js";
import { openDeleteConfirm } from "@/state/drawingSlice.js";

export default function FeatureRow({ feature, layer, onDragStart }) {
  const dispatch = useDispatch();
  const {
    renameFeature,
    removeFeature,
    toggleFeatureVis,
    selectFeatureById,
    selectedFeatureId,
  } = useLayers();
  const isSelected = (feature.backendId && feature.backendId === selectedFeatureId) || (feature.localId === selectedFeatureId);
  const { mapInstance } = useMap();
  const [editing, setEditing] = useState(false);
  const [nameVal, setNameVal] = useState(feature.name);

  const handleRename = () => {
    const t = nameVal.trim();
    if (!t) return;
    if (!/^[a-zA-Z0-9\s]+$/.test(t)) {
      toast.error("Feature name must contain only letters, numbers, and spaces.");
      return;
    }
    if (t.length > 20) {
      toast.error("Feature name cannot exceed 20 characters.");
      return;
    }
    if (t !== feature.name) {
      renameFeature(layer.localId, feature.localId, feature.backendId, t);
    }
    setEditing(false);
  };

  const handleFly = () => {
    const id = feature.backendId || feature.localId;
    selectFeatureById(id);
    LayerRenderer.flyToFeature(id, mapInstance);
  };

  return (
    <div
      className={`flex items-center gap-1.5 pl-7 pr-3 py-2 rounded-lg group transition-colors cursor-default
    ${isSelected ? "bg-blue-100 dark:bg-blue-900/40 border border-blue-300 dark:border-blue-700" : "hover:bg-gray-50 dark:hover:bg-gray-800"}`}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("featureLocalId", feature.localId);
        e.dataTransfer.setData("fromLayerLocalId", layer.localId);
        if (feature.backendId)
          e.dataTransfer.setData("featureBackendId", feature.backendId);
        if (layer.backendId)
          e.dataTransfer.setData("fromLayerBackendId", layer.backendId);
        onDragStart?.();
      }}
    >
      {/* Drag handle */}
      <GripVertical
        size={12}
        className="text-gray-300 dark:text-gray-600 flex-shrink-0 cursor-grab active:cursor-grabbing"
      />

      {/* Color dot */}
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: feature.color || layer.color || "#2563eb" }}
      />

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
          className="flex-1 text-xs border border-blue-300 dark:border-blue-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-white rounded px-1 py-0.5 outline-none min-w-0"
        />
      ) : (
        <span
          className="flex-1 text-xs text-gray-600 dark:text-gray-300 truncate min-w-0 cursor-pointer hover:text-blue-600 dark:hover:text-blue-400"
          onClick={handleFly}
          title={feature.name}
        >
          {feature.name}
        </span>
      )}

      {/* Actions */}
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
        {editing ? (
          <>
            <button
              onClick={handleRename}
              className="p-1 hover:text-green-600 rounded"
            >
              <Check size={11} />
            </button>
            <button
              onClick={() => setEditing(false)}
              className="p-1 hover:text-gray-400 rounded"
            >
              <X size={11} />
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => {
                setEditing(true);
                setNameVal(feature.name);
              }}
              className="p-1 hover:text-blue-500 rounded"
            >
              <Pencil size={11} />
            </button>
            <button
              onClick={handleFly}
              className="p-1 hover:text-blue-500 rounded"
            >
              <Maximize2 size={11} />
            </button>
            <button
              onClick={() => toggleFeatureVis(layer.localId, feature.localId)}
              className="p-1 hover:text-blue-500 rounded"
            >
              {feature.visible ? (
                <Eye size={11} />
              ) : (
                <EyeOff size={11} className="text-gray-300 dark:text-gray-600" />
              )}
            </button>
            <button
              onClick={() =>
                dispatch(
                  openDeleteConfirm({
                    type: "feature",
                    targetId: feature.localId,
                    backendId: feature.backendId,
                    layerLocalId: layer.localId,
                    name: feature.name,
                  })
                )
              }
              className="p-1 hover:text-red-500 rounded"
            >
              <Trash2 size={11} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}
