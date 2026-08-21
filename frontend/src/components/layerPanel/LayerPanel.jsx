import { useState } from "react";
import { Layers, Eye, EyeOff, Trash2, Search, X, Sliders } from "lucide-react";
import { useSelector, useDispatch } from "react-redux";
import { useLayers } from "@/hooks/useLayers.js";
import { toggleResultLayerVisibility, removeResultLayer } from "@/state/resultLayersSlice.js";
import LayerRow from "../layerRow/LayerRow.jsx";
import DataActions from "../dataActions/DataActions.jsx";

export default function LayerPanel() {
  const { items } = useLayers();
  const resultLayers = useSelector((s) => s.resultLayers.resultLayers) || [];
  const dispatch = useDispatch();

  const [activeTab, setActiveTab] = useState("layers");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredItems = items
    .map((layer) => {
      if (!searchQuery.trim()) return layer;

      const query = searchQuery.toLowerCase().trim();
      const layerNameMatches = layer.name?.toLowerCase().includes(query);

      const matchingFeatures = (layer.features || []).filter((f) =>
        f.name?.toLowerCase().includes(query)
      );

      if (layerNameMatches) {
        return layer;
      } else if (matchingFeatures.length > 0) {
        return {
          ...layer,
          features: matchingFeatures,
          expanded: true, // Auto-expand to show matching features
        };
      }
      return null;
    })
    .filter(Boolean);

  const filteredResultLayers = resultLayers.filter(
    (r) =>
      !searchQuery.trim() ||
      r.name?.toLowerCase().includes(searchQuery.toLowerCase().trim())
  );

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm transition-colors">
      {/* Header Tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
        <button
          onClick={() => setActiveTab("layers")}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
            activeTab === "layers"
              ? "border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-900"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100/30 dark:hover:bg-gray-800/10"
          }`}
        >
          <Layers size={13} className="text-gray-500 dark:text-gray-400" />
          <span>Layers</span>
          <span className="flex h-4 w-4 items-center justify-center rounded-full bg-gray-100 dark:bg-gray-800 text-[9px] font-bold text-gray-600 dark:text-gray-300">
            {filteredItems.length + filteredResultLayers.length}
          </span>
        </button>
        <button
          onClick={() => setActiveTab("actions")}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 ${
            activeTab === "actions"
              ? "border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-900"
              : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100/30 dark:hover:bg-gray-800/10"
          }`}
        >
          <Sliders size={13} className="text-gray-500 dark:text-gray-400" />
          <span>Data Actions</span>
        </button>
      </div>

      {activeTab === "layers" ? (
        <>
          {/* Search Bar */}
          <div className="px-3 py-2 border-b border-gray-150 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/30">
            <div className="relative flex items-center">
              <input
                type="text"
                placeholder="Search layers or features..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-xs rounded-lg border border-gray-250 dark:border-gray-700 bg-white dark:bg-gray-800 pl-8 pr-8 py-1.5 text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition placeholder:text-gray-400"
              />
              <Search size={13} className="absolute left-2.5 text-gray-400 pointer-events-none" />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 p-0.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
                >
                  <X size={10} />
                </button>
              )}
            </div>
          </div>

          {/* Layer list */}
          <div className="p-1.5 min-h-[90px] max-h-[300px] overflow-y-auto space-y-1.5">
            {filteredItems.length === 0 && filteredResultLayers.length === 0 && (
              <p className="text-xs text-gray-400 dark:text-gray-500 py-4 text-center">
                {searchQuery ? "No matches found." : "No layers yet. Draw a shape to create one."}
              </p>
            )}

            {filteredItems.map((layer) => (
              <LayerRow key={layer.localId} layer={layer} />
            ))}

            {/* Computed results section */}
            {filteredResultLayers.length > 0 && (
              <div className="border-t border-gray-100 dark:border-gray-800 pt-1.5 mt-1.5 space-y-1.5">
                <span className="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider block px-2 pb-1">
                  Computed results
                </span>
                {filteredResultLayers.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/40 transition"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: r.color }}
                      />
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-300 truncate">
                        {r.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => dispatch(toggleResultLayerVisibility(r.id))}
                        className="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
                        title={r.visible ? "Hide Layer" : "Show Layer"}
                      >
                        {r.visible ? <Eye size={12} /> : <EyeOff size={12} />}
                      </button>
                      <button
                        onClick={() => dispatch(removeResultLayer(r.id))}
                        className="p-1 rounded text-gray-400 hover:text-red-500 transition"
                        title="Delete Layer"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        <DataActions isTabMode={true} />
      )}
    </div>
  );
}
