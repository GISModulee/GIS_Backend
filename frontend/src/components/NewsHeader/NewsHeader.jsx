import { X, Search } from "lucide-react";

export default function NewsHeader({ onClose }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800">
      <div className="flex items-center gap-2.5">
        <Search className="text-blue-500" size={20} />
        <div>
          <h2 className="text-base font-bold text-gray-800 dark:text-white">Fetch from News</h2>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
            Retrieve news and articles matching a geographic area and search criteria.
          </p>
        </div>
      </div>
      <button
        onClick={onClose}
        className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition"
      >
        <X size={18} />
      </button>
    </div>
  );
}
