import { useState } from "react";
import { useDispatch } from "react-redux";
import { setHoveredFeatureId } from "@/state/layersSlice.js";

export default function FeatureSelector({
  label,
  value,
  onChange,
  items,
  placeholder = "— select —",
  disabled = false,
  multiple = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dispatch = useDispatch();

  // Find all features in active layers
  const allFeatures = items.flatMap((l) => l.features || []);

  // Find selected feature names / objects
  const getSelectedDisplay = () => {
    if (multiple) {
      if (!Array.isArray(value) || value.length === 0) return placeholder;
      const selectedNames = allFeatures
        .filter((f) => value.includes(f.localId))
        .map((f) => f.name);
      if (selectedNames.length === 0) return placeholder;
      if (selectedNames.length > 2) return `${selectedNames.length} selected`;
      return selectedNames.join(", ");
    } else {
      const selectedFeature = allFeatures.find((f) => f.localId === value);
      return selectedFeature ? selectedFeature.name : placeholder;
    }
  };

  // Filter out Point, Circle, Polyline/Line features
  const filteredItems = items
    .map((lyr) => {
      const validFeatures = (lyr.features || []).filter((f) => {
        const type = (f.type || "").toLowerCase();
        return (
          type !== "point" &&
          type !== "polyline" &&
          type !== "line" &&
          type !== "linestring"
        );
      });
      return {
        ...lyr,
        features: validFeatures,
      };
    })
    .filter((lyr) => lyr.features.length > 0);

  const handleHoverFeature = (id) => {
    dispatch(setHoveredFeatureId(id));
  };

  const handleItemClick = (localId) => {
    if (multiple) {
      const currentValues = Array.isArray(value) ? value : [];
      const index = currentValues.indexOf(localId);
      let newValues;
      if (index > -1) {
        newValues = currentValues.filter((val) => val !== localId);
      } else {
        newValues = [...currentValues, localId];
      }
      onChange(newValues);
    } else {
      onChange(localId);
      setIsOpen(false);
      handleHoverFeature(null);
    }
  };

  const isSelected = (localId) => {
    if (multiple) {
      return Array.isArray(value) && value.includes(localId);
    }
    return value === localId;
  };

  return (
    <div className="relative">
      <label className="block text-[9px] font-semibold text-gray-500 dark:text-gray-400 mb-0.5">
        {label}
      </label>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-800 rounded text-[11px] text-gray-800 dark:text-gray-200 text-left flex justify-between items-center focus:outline-none focus:border-blue-500 transition-colors disabled:opacity-50"
      >
        <span className="truncate">{getSelectedDisplay()}</span>
        <span className="text-[8px] text-gray-400 dark:text-gray-500">▼</span>
      </button>

      {isOpen && (
        <>
          {/* Backdrop layer to click away and close dropdown */}
          <div className="fixed inset-0 z-[1900]" onClick={() => setIsOpen(false)} />
          <div className="absolute left-0 mt-1 w-full max-h-48 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-[2000] py-1 text-[11px] text-gray-800 dark:text-gray-200">
            {!multiple && (
              <div
                onClick={() => {
                  onChange("");
                  setIsOpen(false);
                  handleHoverFeature(null);
                }}
                className="px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
              >
                {placeholder}
              </div>
            )}
            {filteredItems.map((lyr) => (
              <div key={lyr.localId}>
                <div className="px-2 py-0.5 text-[8px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider bg-gray-50 dark:bg-gray-900/30">
                  {lyr.name}
                </div>
                {lyr.features?.map((f) => {
                  const active = isSelected(f.localId);
                  return (
                    <div
                      key={f.localId}
                      onClick={() => handleItemClick(f.localId)}
                      onMouseEnter={() => handleHoverFeature(f.localId)}
                      onMouseLeave={() => handleHoverFeature(null)}
                      className={`px-3 py-1 flex items-center justify-between cursor-pointer transition-colors ${
                        active
                          ? "bg-blue-500 text-white hover:bg-blue-600"
                          : "hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400"
                      }`}
                    >
                      <span>{f.name}</span>
                      {active && <span className="text-[9px]">✓</span>}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
