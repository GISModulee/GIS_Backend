import { ExternalLink } from "lucide-react";

export default function NewsArticleCard({ article, idx }) {
  return (
    <div
      key={idx}
      className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 hover:border-blue-400 dark:hover:border-blue-500 p-4 rounded-xl transition flex flex-col gap-2.5"
    >
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-xs font-bold text-gray-800 dark:text-white leading-5">
          {article.title || "Untitled Article"}
        </h4>
        {article.url && (
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-600 flex-shrink-0"
            title="Open Article Link"
          >
            <ExternalLink size={14} />
          </a>
        )}
      </div>

      <div className="flex items-center gap-3 text-[10px] text-gray-400 dark:text-gray-500 font-semibold mt-1">
        {article.source && (
          <span className="bg-gray-200 dark:bg-gray-800 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded">
            {article.source}
          </span>
        )}
        {article.published_date && <span>{article.published_date}</span>}
      </div>
    </div>
  );
}
