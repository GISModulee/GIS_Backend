// src/components/saveShapeModal/SaveShapeModal.jsx
import { useState, useEffect } from "react";
import { X, Check } from "lucide-react";
import { useSelector } from "react-redux";
import toast from "react-hot-toast";

const CATEGORIES = ["Terrorist", "Crime", "Surveillance", "Patrol", "Other"];

export default function SaveShapeModal({ type, onSave, onCancel }) {
  const pendingColor = useSelector((s) => s.layers.pendingColor);

  const [name, setName] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [customCategory, setCustomCategory] = useState("");
  const [color, setColor] = useState(pendingColor);

  // When modal opens for a new shape, reset with the shape's color
  useEffect(() => {
    setName("");
    setCategory(CATEGORIES[0]);
    setCustomCategory("");
    setColor(pendingColor); // ← pre-fill with shape color
  }, [type, pendingColor]);

  const handleSave = () => {
    const t = name.trim();
    if (!t) return;

    if (!/^[a-zA-Z0-9\s]+$/.test(t)) {
      toast.error("Feature name must contain only letters, numbers, and spaces.");
      return;
    }

    if (t.length > 20) {
      toast.error("Feature name cannot exceed 20 characters.");
      return;
    }

    const normalizedColor = color.toLowerCase().trim();
    
    // Check if color is black (e.g. #000000, #000, black) or very dark gray near black
    if (normalizedColor === "#000000" || normalizedColor === "#000" || normalizedColor === "black") {
      toast.error("Black is reserved for uploaded data. Please select another color.");
      return;
    }
    
    // Check if color is red (e.g. #ff0000, #ef4444, #dc2626, red)
    if (normalizedColor === "#ff0000" || normalizedColor === "#ef4444" || normalizedColor === "#dc2626" || normalizedColor === "red") {
      toast.error("Red is reserved for added image predictions. Please select another color.");
      return;
    }

    let finalCategory = category;
    if (category === "Other") {
      const trimmedCustom = customCategory.trim();
      if (!trimmedCustom) {
        toast.error("Please enter a custom category name.");
        return;
      }
      finalCategory = trimmedCustom;
    }

    onSave({ name: t, category: finalCategory, color });
  };

  const title = type
    ? `Save ${type.charAt(0).toUpperCase() + type.slice(1)}`
    : "Save Shape";

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-start justify-between px-6 pt-6 pb-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-white">
              {title}
            </h2>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-0.5">
              Enter the metadata for this shape before saving it.
            </p>
          </div>
          <button
            onClick={onCancel}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-4 space-y-5">
          {/* Name */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Name
            </label>
            <input
              autoFocus
              type="text"
              value={name}
              onChange={(e) => {
                const val = e.target.value;
                if (/^[a-zA-Z0-9\s]*$/.test(val) && val.length <= 20) {
                  setName(val);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSave();
              }}
              placeholder="Enter shape name"
              className="w-full rounded-xl border border-gray-200 dark:border-gray-700 dark:text-white bg-gray-50 dark:bg-gray-800 px-4 py-3
                text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100
                transition placeholder:text-gray-300"
            />
          </div>

          {/* Category */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Category
            </label>
            <div className="space-y-2">
              {CATEGORIES.map((cat) => (
                <div key={cat} className="w-full">
                  <label
                    className={`flex items-center gap-3 w-full px-4 py-3 rounded-xl border
                      cursor-pointer transition
                      ${
                        category === cat
                          ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/30"
                          : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700"
                      }`}
                  >
                    <input
                      type="radio"
                      name="category"
                      value={cat}
                      checked={category === cat}
                      onChange={() => setCategory(cat)}
                      className="accent-blue-500"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-200">
                      {cat}
                    </span>
                  </label>

                  {cat === "Other" && category === "Other" && (
                    <input
                      type="text"
                      value={customCategory}
                      onChange={(e) => setCustomCategory(e.target.value)}
                      placeholder="Enter custom category"
                      className="w-full mt-2 rounded-xl border border-gray-200 dark:border-gray-700 dark:text-white bg-gray-50 dark:bg-gray-800 px-4 py-2.5
                        text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100
                        transition placeholder:text-gray-400 dark:placeholder:text-gray-600"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Colour — live preview swatch */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Colour
            </label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="w-10 h-10 rounded-lg border border-gray-200 dark:border-gray-700 dark:bg-gray-800 cursor-pointer p-0.5"
              />
              {/* Live preview bar */}
              <div
                className="flex-1 h-8 rounded-lg border border-gray-200 dark:border-gray-700 transition-all"
                style={{ backgroundColor: color, opacity: 0.7 }}
              />
              <span className="text-sm text-gray-500 font-mono w-20">
                {color}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800">
          <button
            onClick={onCancel}
            className="xx-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim()}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
              bg-blue-600 text-white hover:bg-blue-700 transition
              disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Check size={15} />
            Save shape
          </button>
        </div>
      </div>
    </div>
  );
}
