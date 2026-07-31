import { Search, AlertCircle } from "lucide-react";
import NewsArticleCard from "../NewsArticleCard/NewsArticleCard.jsx";

export default function NewsResultsSection({
  loading,
  errorMsg,
  newsResults,
  filteredNewsResults,
}) {
  return (
    <div className="flex-1 overflow-y-auto p-6 flex flex-col min-h-0">
      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center py-20 gap-3">
          <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-100 border-t-blue-600 dark:border-blue-900/40 dark:border-t-blue-500"></div>
          <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 animate-pulse">
            Querying news articles...
          </span>
        </div>
      )}

      {errorMsg && (
        <div className="flex-1 flex items-center justify-center p-6 text-center">
          <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 rounded-2xl p-6 max-w-md">
            <AlertCircle className="text-red-500 mx-auto mb-2" size={28} />
            <h3 className="text-sm font-bold text-red-800 dark:text-red-300">Search Failed</h3>
            <p className="text-xs text-red-600 dark:text-red-400 mt-1">{errorMsg}</p>
          </div>
        </div>
      )}

      {!loading && !errorMsg && newsResults === null && (
        <div className="flex-1 flex flex-col items-center justify-center py-20 text-center text-gray-400 dark:text-gray-500">
          <Search size={32} className="text-gray-300 mb-2" />
          <h3 className="text-sm font-semibold">No Search Run</h3>
          <p className="text-xs mt-0.5 max-w-xs">
            Configure your parameters and click Search News to retrieve articles.
          </p>
        </div>
      )}

      {!loading && !errorMsg && newsResults !== null && newsResults.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center py-20 text-center text-gray-400 dark:text-gray-500">
          <Search size={32} className="text-gray-300 mb-2" />
          <h3 className="text-sm font-semibold">No Articles Found</h3>
          <p className="text-xs mt-0.5 max-w-xs">
            Try selecting a different geographic area, adjusting dates, or changing keywords.
          </p>
        </div>
      )}

      {!loading && !errorMsg && newsResults !== null && newsResults.length > 0 && filteredNewsResults.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center py-20 text-center text-gray-400 dark:text-gray-500">
          <Search size={32} className="text-gray-300 mb-2" />
          <h3 className="text-sm font-semibold">No Matches Found</h3>
          <p className="text-xs mt-0.5 max-w-xs">
            Try adjusting your keyword filter or choosing a different news source.
          </p>
        </div>
      )}

      {!loading && !errorMsg && filteredNewsResults.length > 0 && (
        <div className="grid grid-cols-1 gap-3.5">
          {filteredNewsResults.map((article, idx) => (
            <NewsArticleCard key={idx} article={article} idx={idx} />
          ))}
        </div>
      )}
    </div>
  );
}
