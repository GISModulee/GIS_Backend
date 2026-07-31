import { useState } from "react";
import { Image as ImageIcon } from "lucide-react";
import AddImageModal from "../addImageModal/AddImageModal.jsx";

export default function AddImageButton() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="flex items-center justify-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-xs font-medium text-gray-700 dark:text-gray-200 shadow-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition"
      >
        <ImageIcon size={14} />
        <span>Add Image</span>
      </button>

      <AddImageModal isOpen={isOpen} onClose={() => setIsOpen(false)} />
    </>
  );
}
