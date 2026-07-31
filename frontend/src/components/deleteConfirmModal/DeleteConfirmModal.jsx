import { X, AlertTriangle } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { closeDeleteConfirm } from "@/state/layersSlice.js";
import { useLayers } from "@/hooks/useLayers.js";

export default function DeleteConfirmModal() {
  const dispatch = useDispatch();
  const { removeLayer, removeFeature } = useLayers();
  const { open, type, targetId, backendId, layerLocalId, name, featuresList } = useSelector(
    (s) => s.layers.deleteConfirm || { open: false }
  );

  if (!open) return null;

  const handleConfirm = async () => {
    if (type === "layer") {
      await removeLayer(targetId, backendId);
    } else if (type === "feature") {
      await removeFeature(layerLocalId, targetId, backendId);
    }
    dispatch(closeDeleteConfirm());
  };

  const handleCancel = () => {
    dispatch(closeDeleteConfirm());
  };

  return (
    <div className="fixed inset-0 z-[2100] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 dark:border-gray-800 transition-colors animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="flex items-start gap-4 px-6 pt-6 pb-2">
          <div className="p-2.5 bg-red-50 dark:bg-red-950/30 rounded-xl text-red-600 dark:text-red-400 flex-shrink-0">
            <AlertTriangle size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Delete {type === "layer" ? "Layer" : "Feature"}
            </h2>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-0.5 truncate">
              "{name}"
            </p>
          </div>
          <button
            onClick={handleCancel}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-3">
          {type === "feature" ? (
            <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
              Confirm if you want to delete the feature. This action cannot be undone.
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                Deleting this layer will delete the following feature(s) inside it:
              </p>
              {featuresList.length > 0 ? (
                <div className="max-h-28 overflow-y-auto bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-100 dark:border-gray-800 p-3 space-y-1">
                  {featuresList.map((f, i) => (
                    <div key={i} className="text-xs text-gray-600 dark:text-gray-400 truncate flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-red-400" />
                      {f.name || "Untitled Feature"}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400 italic dark:text-gray-500">
                  (No features in this layer)
                </p>
              )}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
          <button
            onClick={handleCancel}
            className="px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold bg-red-600 hover:bg-red-700 text-white shadow-sm transition"
          >
            Delete
          </button>
        </div>

      </div>
    </div>
  );
}
