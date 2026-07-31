// src/components/leftSidebar/LeftSidebar.jsx
import { useState } from "react";
import {
  Search,
  Layers,
} from "lucide-react";
import DataSourceCard from "../dataSourceCard/DataSourceCard";
import UploadData from "../uploadData/UploadData.jsx";
import AddImageButton from "../addImageButton/AddImageButton.jsx";
import LayerPanel from "../layerPanel/LayerPanel.jsx";
import DataActions from "../dataActions/DataActions.jsx";
import FetchNewsModal from "../fetchNewsModal/FetchNewsModal.jsx";

// ── Main sidebar ──────────────────────────────────────────
export default function LeftSidebar({ isOpen, onClose }) {
  const [showDataSources, setShowDataSources] = useState(false);
  const [showNewsModal, setShowNewsModal] = useState(false);

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-black/30 z-10 md:hidden"
        />
      )}

      <aside
        className={`fixed top-14 left-0 h-[calc(100vh-56px)] w-72 bg-gray-50 dark:bg-gray-950 border-r
          border-gray-200 dark:border-gray-800 z-20 flex flex-col transition-all duration-300
          ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Upload buttons */}
          <div className="grid grid-cols-2 gap-2">
            <UploadData />
            <AddImageButton />
          </div>

          {/* Layer panel */}
          <LayerPanel />

          {/* Data Actions Section */}
          <DataActions />
        </div>

        <div className="border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 p-4">
          <button
            onClick={() => setShowDataSources((v) => !v)}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-200 shadow-sm transition hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <Search size={16} />
            <span>Browse Data Hub</span>
          </button>
        </div>
      </aside>

      {showDataSources && (
        <div className="fixed z-[1200]" style={{ bottom: 80, left: 288 + 12 }}>
          <DataSourceCard
            onClose={() => setShowDataSources(false)}
            onSelect={(source) => {
              setShowDataSources(false);
              if (source === "news") {
                setShowNewsModal(true);
              }
            }}
          />
        </div>
      )}

      {showNewsModal && (
        <FetchNewsModal onClose={() => setShowNewsModal(false)} />
      )}
    </>
  );
}
