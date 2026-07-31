import { useRef } from "react";
import { Upload, File } from "lucide-react";

export default function AddImageUpload({
  selectedFile,
  preview,
  isDragOver,
  loading,
  onChangeFile,
  onDragOver,
  onDragLeave
}) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) onChangeFile(file);
  };

  const handleDropLocal = (e) => {
    e.preventDefault();
    onDragLeave();
    const file = e.dataTransfer.files[0];
    if (file) onChangeFile(file);
  };

  return (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-gray-700 dark:text-gray-300">
        Upload File
      </label>
      
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,.tif,.tiff"
        className="hidden"
        onChange={handleFileChange}
        disabled={loading}
      />

      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={handleDropLocal}
        onClick={() => !loading && fileInputRef.current?.click()}
        className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition
          ${isDragOver 
            ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20" 
            : "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 hover:bg-gray-100 dark:hover:bg-gray-800"
          } ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        {preview ? (
          <div className="relative w-full max-h-32 flex items-center justify-center overflow-hidden rounded-lg">
            <img src={preview} alt="Upload preview" className="max-h-28 object-contain" />
          </div>
        ) : selectedFile ? (
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
        Supported formats: PNG, JPEG (.png, .jpeg)
      </p>
    </div>
  );
}
