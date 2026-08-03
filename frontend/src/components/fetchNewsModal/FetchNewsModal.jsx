import { useState, useEffect } from "react";
import { useSelector } from "react-redux";
import { createPortal } from "react-dom";
import { useLayers } from "@/hooks/useLayers.js";
import axiosInstance from "@/api/axiosInstance.js";
import toast from "react-hot-toast";
import { getErrorMessage } from "@/utils/ErrorUtils.js";

// Sub-components
import NewsHeader from "@/components/NewsHeader/NewsHeader.jsx";
import NewsSearchForm from "@/components/NewsSearchForm/NewsSearchForm.jsx";
import NewsFilterBar from "@/components/NewsFilterBar/NewsFilterBar.jsx";
import NewsResultsSection from "@/components/NewsResultsSection/NewsResultsSection.jsx";

export default function FetchNewsModal({ onClose }) {
  const { items } = useLayers();
  const allFeatures = items.flatMap((layer) => layer.features || []);
  const selectedFeatureIdFromStore = useSelector((state) => state.layers.selectedFeatureId);

  const [selectedFeatureId, setSelectedFeatureId] = useState("");
  const [keywords, setKeywords] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [maxResults, setMaxResults] = useState(10);

  const [loading, setLoading] = useState(false);
  const [newsResults, setNewsResults] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const [newsSearchQuery, setNewsSearchQuery] = useState("");
  const [selectedDateFilter, setSelectedDateFilter] = useState("");
  const [isFeatureDropdownOpen, setIsFeatureDropdownOpen] = useState(false);

  // Get unique formatted dates for the filter dropdown
  const uniqueDates = (() => {
    if (!newsResults) return [];
    const dates = newsResults.map((r) => r.published_date).filter(Boolean);
    return Array.from(new Set(dates)).sort((a, b) => new Date(b) - new Date(a));
  })();

  // Filter news results by text search and selected date
  const filteredNewsResults = (() => {
    if (!newsResults) return [];
    return newsResults.filter((article) => {
      const matchesSearch =
        !newsSearchQuery.trim() ||
        (article.title || "").toLowerCase().includes(newsSearchQuery.toLowerCase().trim()) ||
        (article.summary || "").toLowerCase().includes(newsSearchQuery.toLowerCase().trim());

      const matchesDate = !selectedDateFilter || article.published_date === selectedDateFilter;

      return matchesSearch && matchesDate;
    });
  })();

  // Auto-select selected feature from store or first feature if available
  useEffect(() => {
    if (selectedFeatureIdFromStore) {
      const found = allFeatures.find(
        (f) =>
          f.backendId === selectedFeatureIdFromStore || f.localId === selectedFeatureIdFromStore
      );
      if (found) {
        setSelectedFeatureId(found.localId || found.backendId);
        return;
      }
    }
    if (allFeatures.length > 0 && !selectedFeatureId) {
      setSelectedFeatureId(allFeatures[0].localId || allFeatures[0].backendId);
    }
  }, [items, selectedFeatureIdFromStore]);

  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setNewsResults(null);
    setNewsSearchQuery("");
    setSelectedDateFilter("");

    const feat = allFeatures.find(
      (f) => f.localId === selectedFeatureId || f.backendId === selectedFeatureId
    );
    if (!feat || !feat.feature_number || !feat.case_id || !feat.layer_id) {
      toast.error("Please select a saved geographic feature first");
      setLoading(false);
      return;
    }

    const keywordList = keywords
      ? keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean)
      : [];

    if (keywordList.length > 5) {
      toast.error("Please enter a maximum of 5 keywords");
      setLoading(false);
      return;
    }

    const hasOverLongKeyword = keywordList.some((k) => k.length > 20);
    if (hasOverLongKeyword) {
      toast.error("Each keyword must be at most 20 characters long");
      setLoading(false);
      return;
    }

    const payload = {
      case_id: Number(feat.case_id),
      layer_id: Number(feat.layer_id),
      feature_number: Number(feat.feature_number),
      keywords: keywordList,
      start_date: new Date(startDate).toISOString(),
      end_date: new Date(endDate).toISOString(),
      max_results: maxResults === "" ? 10 : Number(maxResults),
    };

    try {
      console.log("[FetchNews] Searching news with payload:", payload);
      const response = await axiosInstance.post("/geo-search/news", payload);
      console.log("[FetchNews] Response:", response.data);

      let articlesArray = [];
      if (response.data) {
        if (Array.isArray(response.data)) {
          articlesArray = response.data;
        } else if (response.data.articles && Array.isArray(response.data.articles)) {
          articlesArray = response.data.articles;
        } else if (response.data.news && Array.isArray(response.data.news)) {
          articlesArray = response.data.news;
        } else if (response.data.results && Array.isArray(response.data.results)) {
          articlesArray = response.data.results;
        } else if (response.data.data && Array.isArray(response.data.data)) {
          articlesArray = response.data.data;
        } else {
          // Dynamic fallback scan for any array property
          const keys = Object.keys(response.data);
          for (const key of keys) {
            if (Array.isArray(response.data[key])) {
              articlesArray = response.data[key];
              break;
            }
          }
        }
      }

      const articles = articlesArray.map((article) => {
        let title = article.title || "";
        let url = article.url || article.link || "";

        // Extract URL from HTML if not present
        if (typeof title === "string" && title.includes("href=") && !url) {
          const hrefMatch = title.match(/href="([^"]+)"/);
          if (hrefMatch) {
            url = hrefMatch[1];
          }
        }

        const stripHtml = (html) => {
          if (!html || typeof html !== "string") return "";
          let text = html.replace(/<[^>]*>/g, "");
          text = text
            .replace(/&nbsp;/g, " ")
            .replace(/&amp;/g, "&")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">")
            .replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'");
          return text.trim();
        };

        const cleanedTitle = stripHtml(title);
        const cleanedSummary = stripHtml(
          article.summary || article.description || article.content || article.snippet || ""
        );
        const sourceVal = article.source || article.source_name || article.publisher || "";

        let finalTitle = cleanedTitle;
        if (sourceVal && typeof sourceVal === "string") {
          const escapedSource = sourceVal.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&");
          const sourceRegex = new RegExp(`\\s*(?:-|\\||—)?\\s*${escapedSource}\\s*$`, "i");
          finalTitle = cleanedTitle.replace(sourceRegex, "").trim();
        }

        const formatDate = (dateStr) => {
          if (!dateStr) return "";
          let parsed = new Date(dateStr);
          if (isNaN(parsed.getTime())) {
            const num = Number(dateStr);
            if (!isNaN(num) && num > 0) {
              if (num < 10000000000) {
                parsed = new Date(num * 1000);
              } else {
                parsed = new Date(num);
              }
            }
          }
          if (!isNaN(parsed.getTime())) {
            return parsed.toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              timeZone: "UTC", // Use UTC to prevent local-timezone offset shifting dates
            });
          }
          return String(dateStr);
        };

        // Scan keys for dates
        let dateVal = "";
        const knownDateKeys = [
          "published_date",
          "publishedAt",
          "pubDate",
          "date",
          "published",
          "time",
          "created_at",
        ];
        for (const k of knownDateKeys) {
          if (article[k]) {
            dateVal = article[k];
            break;
          }
        }
        if (!dateVal) {
          for (const k of Object.keys(article)) {
            const keyLower = k.toLowerCase();
            if (
              (keyLower.includes("date") || keyLower.includes("time") || keyLower.includes("pub")) &&
              article[k]
            ) {
              dateVal = article[k];
              break;
            }
          }
        }

        const formattedDate = formatDate(dateVal);

        return {
          ...article,
          title: finalTitle || "Untitled Article",
          url,
          summary: cleanedSummary,
          published_date: formattedDate,
          source: sourceVal,
        };
      });

      setNewsResults(articles);
    } catch (err) {
      console.error("[FetchNews] Error:", err);
      setErrorMsg(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden border border-gray-100 dark:border-gray-800 transition-colors">
        
        {/* Header */}
        <NewsHeader onClose={onClose} />

        {/* Content body - Split layout */}
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {/* Left panel: Form configuration */}
          <NewsSearchForm
            handleSearch={handleSearch}
            loading={loading}
            allFeatures={allFeatures}
            selectedFeatureId={selectedFeatureId}
            setSelectedFeatureId={setSelectedFeatureId}
            isFeatureDropdownOpen={isFeatureDropdownOpen}
            setIsFeatureDropdownOpen={setIsFeatureDropdownOpen}
            keywords={keywords}
            setKeywords={setKeywords}
            startDate={startDate}
            setStartDate={setStartDate}
            endDate={endDate}
            setEndDate={setEndDate}
            maxResults={maxResults}
            setMaxResults={setMaxResults}
          />

          {/* Right panel: Results display */}
          <div className="flex-1 bg-white dark:bg-gray-950 flex flex-col min-h-0">
            {/* Filter controls at the top of results panel */}
            <NewsFilterBar
              newsResults={newsResults}
              filteredNewsResults={filteredNewsResults}
              selectedDateFilter={selectedDateFilter}
              setSelectedDateFilter={setSelectedDateFilter}
              uniqueDates={uniqueDates}
              newsSearchQuery={newsSearchQuery}
              setNewsSearchQuery={setNewsSearchQuery}
            />

            {/* Main results list showing articles or status cards */}
            <NewsResultsSection
              loading={loading}
              errorMsg={errorMsg}
              newsResults={newsResults}
              filteredNewsResults={filteredNewsResults}
            />
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
