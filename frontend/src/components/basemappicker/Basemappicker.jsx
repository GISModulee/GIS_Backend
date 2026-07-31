import { X } from "lucide-react";

export default function Basemappicker({
  options,
  selected,
  onSelect,
  onClose,
}) {
  return (
    <div className="w-48 bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-100 dark:border-gray-700 p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-900 dark:text-gray-100">
          Basemap
        </h3>
        <button
          onClick={onClose}
          className="w-5 h-5 flex items-center justify-center rounded-md text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-200 transition"
        >
          <X size={14} />
        </button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-1.5">
        {options.map((opt) => {
          const isActive = selected === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => onSelect(opt.id)}
              className={`flex flex-col items-center gap-1 rounded-lg border p-1.5 transition ${
                isActive
                  ? "border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-blue-900/30"
                  : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700"
              }`}
            >
              <span className={`w-full h-6 rounded-md ${opt.swatchClass}`} />
              <span
                className={`text-[10px] text-center leading-tight font-medium ${
                  isActive
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-700 dark:text-gray-300"
                }`}
              >
                {opt.label}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// IDs must exactly match the keys in src/config/mapProviders.js
export const BASEMAP_OPTIONS = [
  {
    id: "custom",
    label: "Custom Tiles",
    swatchClass: "bg-blue-600",
  },
  {
    id: "esriSatellite",
    label: "ESRI Satellite",
    swatchClass: "bg-green-800",
  },
  {
    id: "cartoLight",
    label: "Carto Light",
    swatchClass: "bg-gray-200",
  },
  {
    id: "dark",
    label: "Carto Dark",
    swatchClass: "bg-gray-900",
  },
  {
    id: "esriStreet",
    label: "ESRI Street",
    swatchClass: "bg-blue-600",
  },
  {
    id: "windy",
    label: "Weather (Windy)",
    swatchClass: "bg-sky-400",
  },
];