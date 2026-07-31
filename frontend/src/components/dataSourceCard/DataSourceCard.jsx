import { X, ChevronRight, Newspaper, Brain, Share2 } from "lucide-react";

export default function DataSourceCard({ onClose, onSelect }) {
  const sources = [
    {
      id: "news",
      title: "Fetch from News",
      subtitle: "News & Articles",
      icon: Newspaper,
    },
    {
      id: "model",
      title: "Fetch from Model",
      subtitle: "ML Predictions",
      icon: Brain,
    },
    {
      id: "social",
      title: "Fetch from Social",
      subtitle: "Social Media",
      icon: Share2,
    },
  ];

  return (
    <div className="translate-y-12 w-56 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          Data Sources
        </h2>

        <button
          onClick={onClose}
          className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
        >
          <X size={14} className="text-gray-500" />
        </button>
      </div>

      <div className="border-t border-gray-200 dark:border-gray-700" />

      {/* Options */}
      <div className="py-1">
        {sources.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className="w-full flex items-center px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
            >
              <div className="w-8 h-8 rounded-md bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center shrink-0">
                <Icon size={16} className="text-blue-600 dark:text-blue-400" />
              </div>

              <div className="flex-1 ml-2.5 text-left">
                <h3 className="text-xs font-semibold text-gray-900 dark:text-gray-100">
                  {item.title}
                </h3>

                <p className="text-[11px] text-gray-500 leading-4">
                  {item.subtitle}
                </p>
              </div>

              <ChevronRight size={14} className="text-gray-400" />
            </button>
          );
        })}
      </div>
    </div>
  );
}