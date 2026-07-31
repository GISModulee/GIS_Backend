import { Search, X } from "lucide-react";

export default function NewsFilterBar({
  newsResults,
  filteredNewsResults,
  selectedDateFilter,
  setSelectedDateFilter,
  uniqueDates,
  newsSearchQuery,
  setNewsSearchQuery,
}) {
  if (!newsResults || newsResults.length === 0) return null;

  return (
    <div className="p-6 pb-3 border-b border-gray-100 dark:border-gray-800 space-y-3 flex-shrink-0 bg-gray-50/20 dark:bg-gray-900/10">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <span className="text-xs font-bold text-gray-700 dark:text-gray-300">
          Search Results ({filteredNewsResults.length} / {newsResults.length})
        </span>
        {/* Date Filter Select */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-[10px] uppercase font-bold text-gray-400">Date:</span>
          <select
            value={selectedDateFilter}
            onChange={(e) => setSelectedDateFilter(e.target.value)}
            className="text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-gray-800 dark:text-white outline-none focus:border-blue-400 transition min-w-[120px]"
          >
            <option value="">All Dates</option>
            {uniqueDates.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      </div>
      {/* Text Search inside results */}
      <div className="relative flex items-center">
        <input
          type="text"
          placeholder="Filter articles by text..."
          value={newsSearchQuery}
          onChange={(e) => setNewsSearchQuery(e.target.value)}
          className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 pl-8 pr-8 py-1.5 text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition placeholder:text-gray-400"
        />
        <Search size={13} className="absolute left-2.5 text-gray-400 pointer-events-none" />
        {newsSearchQuery && (
          <button
            onClick={() => setNewsSearchQuery("")}
            className="absolute right-2.5 p-0.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition"
          >
            <X size={10} />
          </button>
        )}
      </div>
    </div>
  );
}
