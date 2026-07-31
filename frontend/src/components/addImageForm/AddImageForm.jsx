import { Info } from "lucide-react";

export default function AddImageForm({
  layerName,
  setLayerName,
  numPredictions,
  setNumPredictions,
  loading
}) {
  return (
    <div className="space-y-4">
      {/* Layer Name */}
      <div className="space-y-1">
        <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
          Layer Name
        </label>
        <input
          type="text"
          required
          value={layerName}
          onChange={(e) => setLayerName(e.target.value)}
          placeholder="Enter layer name"
          disabled={loading}
          className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2
            text-xs text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900/30
            transition placeholder:text-gray-400 dark:placeholder:text-gray-600"
        />
      </div>

      {/* Number of Predictions */}
      <div className="space-y-1">
        <div className="flex items-center gap-1.5 mb-1">
          <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
            Number of Predictions
          </label>
          <div className="relative group inline-block">
            <Info size={13} className="text-gray-400 dark:text-gray-500 hover:text-blue-500 dark:hover:text-blue-400 cursor-help transition-colors" />
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 p-2.5 bg-gray-900 dark:bg-gray-800 text-white text-[10px] rounded-lg shadow-xl opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 z-[2100] text-left font-normal leading-normal border border-gray-800 dark:border-gray-700">
              Defines the maximum number of objects/predictions identified in the uploaded image.
              <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-[6px] border-transparent border-t-gray-900 dark:border-t-gray-800" />
            </div>
          </div>
        </div>
        <input
          type="number"
          min="1"
          max="20"
          required
          value={numPredictions}
          onChange={(e) => setNumPredictions(Math.min(20, Math.max(1, parseInt(e.target.value, 10) || 1)))}
          disabled={loading}
          className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2
            text-xs text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900/30
            transition"
        />
      </div>
    </div>
  );
}
