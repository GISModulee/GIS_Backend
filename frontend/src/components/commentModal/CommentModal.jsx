// src/components/commentModal/CommentModal.jsx
import { useState, useRef } from "react";
import { X, Check, Paperclip, FileText } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";
import { closeCommentModal } from "@/state/layersSlice.js";
import layerService from "@/utils/layerService.js";
import { useMap } from "@/hooks/useMap.js";
import { useLayers } from "@/hooks/useLayers.js";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/utils/ErrorUtils.js";

export default function CommentModal() {
  const dispatch = useDispatch();
  const { changeActiveTool } = useMap();
  const { loadLayersFromBackend } = useLayers();
  const { open, featureBackendId } = useSelector((s) => s.layers.commentModal);

  const [comment, setComment] = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileRef = useRef(null);

  if (!open) return null;

  const handleImage = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setImageFile(file);
    if (file.type.startsWith("image/")) {
      setPreview(URL.createObjectURL(file));
    } else {
      setPreview(null);
    }
  };

  const handleSubmit = async () => {
    if (!comment.trim()) return;
    setLoading(true);
    try {
      await layerService.addComment(featureBackendId, comment.trim(), 1, imageFile);
      setComment("");
      setImageFile(null);
      setPreview(null);
      dispatch(closeCommentModal());
      changeActiveTool("select");
      await loadLayersFromBackend();
      toast.success("Comment saved successfully!");
    } catch (err) {
      console.error("[CommentModal] error:", err);
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    setComment("");
    setImageFile(null);
    setPreview(null);
    dispatch(closeCommentModal());
    changeActiveTool("select");
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden border border-gray-100 dark:border-gray-800 transition-colors">

        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-800 dark:text-white">Add Comment</h2>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-0.5">
              Add a comment to the selected shape.
            </p>
          </div>
          <button
            onClick={handleCancel}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Comment text */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Comment</label>
            <textarea
              autoFocus
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              placeholder="Write your comment..."
              className="w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-4 py-3
                text-sm text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900/30
                transition placeholder:text-gray-300 dark:placeholder:text-gray-600 resize-none"
            />
          </div>

          {/* Attachment upload */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Attachment <span className="text-gray-400 dark:text-gray-500 font-normal">(optional)</span>
            </label>
            <input
              ref={fileRef}
              type="file"
              accept="image/*,.pdf,.doc,.docx,.txt"
              className="hidden"
              onChange={handleImage}
            />
            {imageFile ? (
              <div className="relative border border-gray-200 dark:border-gray-700 rounded-xl p-3 bg-gray-50 dark:bg-gray-800">
                {preview ? (
                  <img
                    src={preview}
                    alt="preview"
                    className="w-full h-36 object-cover rounded-lg border border-gray-150 dark:border-gray-700"
                  />
                ) : (
                  <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300 py-4 justify-center">
                    <FileText className="text-blue-500" size={24} />
                    <span className="text-sm font-semibold truncate max-w-xs">{imageFile.name}</span>
                  </div>
                )}
                <button
                  onClick={() => { setImageFile(null); setPreview(null); }}
                  className="absolute top-2 right-2 bg-white dark:bg-gray-800 rounded-full p-1 shadow border border-gray-200 dark:border-gray-700
                    hover:bg-red-50 dark:hover:bg-red-950/30 hover:text-red-500 transition"
                >
                  <X size={13} />
                </button>
              </div>
            ) : (
              <button
                onClick={() => fileRef.current?.click()}
                className="flex items-center gap-2 w-full px-4 py-3 rounded-xl border border-dashed
                  border-gray-300 dark:border-gray-700 text-sm text-gray-400 dark:text-gray-500 hover:border-blue-400 hover:text-blue-500
                  transition bg-gray-50 dark:bg-gray-800"
              >
                <Paperclip size={15} />
                Click to attach a file (Image, PDF, DOC, TXT)
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
          <button
            onClick={handleCancel}
            className="px-5 py-2.5 rounded-xl text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!comment.trim() || loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold
              bg-blue-600 text-white hover:bg-blue-700 transition
              disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Check size={15} />
            {loading ? "Saving…" : "Save comment"}
          </button>
        </div>
      </div>
    </div>
  );
}