import { useState } from "react";
import { createPortal } from "react-dom";
import { useSelector } from "react-redux";
import { Image as ImageIcon, X } from "lucide-react";
import layerService from "@/utils/layerService.js";
import { useLayers } from "@/hooks/useLayers.js";
import axiosInstance from "@/api/axiosInstance.js";
import toast from "react-hot-toast";
import AddImageForm from "../addImageForm/AddImageForm.jsx";
import AddImageUpload from "../addImageUpload/AddImageUpload.jsx";

export default function AddImageModal({ isOpen, onClose }) {
  const [layerName, setLayerName] = useState("");
  const [numPredictions, setNumPredictions] = useState(5);
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const { loadLayersFromBackend, chooseLayer, expandLayer, items } = useLayers();
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const handleClose = () => {
    if (loading) return;
    setLayerName("");
    setNumPredictions(5);
    setSelectedFile(null);
    setPreview("");
    onClose();
  };

  if (!isOpen) return null;

  const handleFileChange = (file) => {
    if (!file) return;

    setSelectedFile(file);
    if (!layerName) {
      const nameWithoutExt = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
      setLayerName(nameWithoutExt);
    }
    if (file.type.startsWith("image/")) {
      setPreview(URL.createObjectURL(file));
    } else {
      setPreview("");
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      toast.error("Please select an image file first");
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

    const resolvedLayerName = layerName.trim() || selectedFile.name;
    const normalizedName = resolvedLayerName.toLowerCase().trim();
    const duplicateExists = items?.some(
      (l) => l.name?.toLowerCase().trim() === normalizedName
    );
    if (duplicateExists) {
      toast.error(`Layer name "${resolvedLayerName}" already exists.`);
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("case_id", activeCaseId);
    formData.append("top_k", numPredictions);
    formData.append("layer_name", resolvedLayerName);

    try {
      console.log("Uploading image layer...", selectedFile);

      const response = await axiosInstance.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const result = response.data;

      console.log("=== Upload Response ===", result);

      if (result.layer_id) {
        try {
          await layerService.replaceLayer(result.layer_id, {
            case_id: activeCaseId,
            name: resolvedLayerName,
            layer_type: "group",
            visible: true,
            color: "#ff0000",
          });
          expandLayer(`local_${result.layer_id}`);
          chooseLayer(`local_${result.layer_id}`);
        } catch (e) {
          console.error("Failed to rename and assign layer to case", e);
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

      toast.success(result?.message || result?.detail || "Image uploaded successfully!");
      handleClose();
    } catch (err) {
      console.error("Upload Error:", err);
      toast.error(err.response?.data?.message || err.response?.data?.detail || err.message || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 dark:border-gray-800 transition-colors">

        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-white flex items-center gap-2">
              <ImageIcon size={18} className="text-blue-500" />
              Add Image Layer
            </h2>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              Upload an image to locate coordinates and create predictions.
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
          <AddImageForm
            layerName={layerName}
            setLayerName={setLayerName}
            numPredictions={numPredictions}
            setNumPredictions={setNumPredictions}
            loading={loading}
          />

          <AddImageUpload
            selectedFile={selectedFile}
            preview={preview}
            isDragOver={isDragOver}
            loading={loading}
            onChangeFile={handleFileChange}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          />

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
  );
}
