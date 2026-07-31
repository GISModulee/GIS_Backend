import { useState, useRef } from "react";
import { createPortal } from "react-dom";
import { useSelector } from "react-redux";
import { Upload, X, File } from "lucide-react";
import { useLayers } from "@/hooks/useLayers.js";
import layerService from "@/utils/layerService.js";
import { API_URLS } from "@/config/apiConfig.js";
import toast from "react-hot-toast";

export default function UploadData() {
  const fileInputRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);
  const [layerName, setLayerName] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const { loadLayersFromBackend, items } = useLayers();
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const handleOpen = () => {
    setIsOpen(true);
    setLayerName("");
    setSelectedFile(null);
  };

  const handleClose = () => {
    if (loading) return;
    setIsOpen(false);
    setLayerName("");
    setSelectedFile(null);
  };

  const handleFileChange = (file) => {
    if (!file) return;

    setSelectedFile(file);
    if (!layerName) {
      const nameWithoutExt = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      setLayerName(nameWithoutExt);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileChange(file);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      toast.error("Please select a data file first");
      return;
    }

    // Check if already uploaded
    const uploadedKey = `uploaded_files_${activeCaseId}`;
    const uploadedList = JSON.parse(localStorage.getItem(uploadedKey) || "[]");
    const isAlreadyUploaded = uploadedList.some(
      (f) => f.name === selectedFile.name && f.size === selectedFile.size
    );

    if (isAlreadyUploaded) {
      toast.error("already uploaded");
      return;
    }

    const resolvedName = layerName.trim() || selectedFile.name;
    const normalizedName = resolvedName.toLowerCase().trim();
    const duplicateExists = items?.some(
      (l) => l.name?.toLowerCase().trim() === normalizedName
    );
    if (duplicateExists) {
      toast.error(`Layer name "${resolvedName}" already exists.`);
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append("case_id", activeCaseId);
    formData.append("file", selectedFile);
    formData.append("layer_name", resolvedName);
    formData.append("name", resolvedName);

    try {
      console.log("Uploading data file...", selectedFile);

      const token = localStorage.getItem("token");
      const response = await fetch(
        `${API_URLS.LAYERS}/import?case_id=${activeCaseId}&layer_name=${encodeURIComponent(resolvedName)}`,
        {
          method: "POST",
          headers: {
            "ngrok-skip-browser-warning": "true",
            ...(token && { "Authorization": `Bearer ${token}` }),
          },
          body: formData,
        },
      );

      if (!response.ok) {
        let errorMsg = "Data upload failed";
        try {
          const errData = await response.json();
          errorMsg = errData.detail || errData.message || JSON.stringify(errData);
        } catch (_) {
          try {
            errorMsg = await response.text();
          } catch (_) { }
        }
        throw new Error(errorMsg);
      }

      const result = await response.json();
      console.log("=== Data Upload Response ===", result);

      if (result.layer_id) {
        try {
          await layerService.replaceLayer(result.layer_id, {
            case_id: activeCaseId,
            name: layerName.trim() || selectedFile.name,
            layer_type: "group",
            visible: true,
          });
        } catch (e) {
          console.error("Failed to rename uploaded data layer", e);
        }
      }

      await loadLayersFromBackend();

      // Record successfully uploaded file
      const uploadedKey = `uploaded_files_${activeCaseId}`;
      const uploadedList = JSON.parse(localStorage.getItem(uploadedKey) || "[]");
      if (!uploadedList.some((f) => f.name === selectedFile.name && f.size === selectedFile.size)) {
        uploadedList.push({ name: selectedFile.name, size: selectedFile.size });
        localStorage.setItem(uploadedKey, JSON.stringify(uploadedList));
      }

      toast.success(result?.message || result?.detail || "Data uploaded and saved successfully!");
      setLayerName("");
      setSelectedFile(null);
      setIsOpen(false);
    } catch (err) {
      console.error("Data Upload Error:", err);
      toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Data upload failed");
    } finally {
      setLoading(false);
    }

  };

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className="flex items-center justify-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 shadow-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition"
      >
        <Upload size={14} />
        <span>Upload Data</span>
      </button>

      {isOpen && createPortal(
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 dark:border-gray-800 transition-colors">

            {/* Header */}
            <div className="flex items-start justify-between px-6 pt-6 pb-2">
              <div>
                <h2 className="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
                  <Upload size={18} className="text-blue-500" />
                  Upload Spatial Data
                </h2>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  Import spatial files directly onto your map layer.
                </p>
              </div>
              <button
                onClick={handleClose}
                disabled={loading}
                className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition disabled:opacity-50"
              >
                <X size={18} />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleUpload} className="px-6 py-4 space-y-4">
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

              {/* Drag and Drop Zone */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
                  Upload File
                </label>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".kml,.csv,.tiff,.tif,.json,.geojson"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files[0])}
                  disabled={loading}
                />

                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => !loading && fileInputRef.current?.click()}
                  className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition
                    ${isDragOver
                      ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20"
                      : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 hover:bg-gray-100 dark:hover:bg-gray-800"
                    } ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  {selectedFile ? (
                    <div className="flex flex-col items-center gap-1.5 text-gray-600 dark:text-gray-300">
                      <File className="text-blue-500" size={24} />
                      <span className="text-xs font-medium truncate max-w-xs">{selectedFile.name}</span>
                      <span className="text-[10px] text-gray-400">{(selectedFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-1.5 text-gray-400 dark:text-gray-500">
                      <Upload size={20} className="text-gray-400" />
                      <span className="text-xs font-medium text-gray-600 dark:text-gray-300">
                        Drag & drop or <span className="text-blue-500 hover:underline">browse</span>
                      </span>
                    </div>
                  )}
                </div>

                <p className="text-[10px] text-gray-400 dark:text-gray-500 text-center mt-1">
                  Supported formats: KML, CSV, GeoTIFF, JSON, GeoJSON (.kml, .csv, .tiff, .tif, .json, .geojson)
                </p>
              </div>

              {/* Actions Footer */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={loading}
                  className="px-4 py-2 rounded-lg text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || loading}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold
                    bg-blue-600 hover:bg-blue-700 text-white transition
                    disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {loading ? "Uploading…" : "Upload Layer"}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
