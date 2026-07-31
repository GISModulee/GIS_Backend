import { Calendar, Sliders, Layers, Info } from "lucide-react";

export default function NewsSearchForm({
  handleSearch,
  loading,
  allFeatures,
  selectedFeatureId,
  setSelectedFeatureId,
  isFeatureDropdownOpen,
  setIsFeatureDropdownOpen,
  keywords,
  setKeywords,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  maxResults,
  setMaxResults,
}) {
  const todayStr = new Date().toISOString().split("T")[0];

  return (
    <form
      onSubmit={handleSearch}
      className="w-full md:w-[380px] p-5 border-r border-gray-100 dark:border-gray-800 overflow-y-auto space-y-4 shrink-0 bg-gray-50/50 dark:bg-gray-900/30"
    >
      {/* Geographic Area Selection */}
      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
          Geographic Area
        </label>
        <div className="space-y-3 p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-150 dark:border-gray-700 shadow-sm">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
              <Layers size={13} className="text-gray-400" />
              Select Feature
            </label>
            {allFeatures.length === 0 ? (
              <div className="text-xs text-amber-500 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 p-2.5 rounded-lg">
                No features found on the map. Draw a shape or import data first.
              </div>
            ) : (() => {
              const selectedFeature = allFeatures.find(
                (f) => (f.localId || f.backendId) === selectedFeatureId
              );
              return (
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setIsFeatureDropdownOpen(!isFeatureDropdownOpen)}
                    className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition flex justify-between items-center text-left"
                  >
                    <span className="truncate">
                      {selectedFeature
                        ? `${selectedFeature.name} (${selectedFeature.type})`
                        : "Select a feature"}
                    </span>
                    <span className="text-[9px] text-gray-400 ml-1">▼</span>
                  </button>

                  {isFeatureDropdownOpen && (
                    <>
                      {/* Backdrop to close click away */}
                      <div
                        className="fixed inset-0 z-[2100]"
                        onClick={() => setIsFeatureDropdownOpen(false)}
                      />
                      <div className="absolute left-0 mt-1 w-full max-h-48 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-250 dark:border-gray-700 rounded-lg shadow-lg z-[2200] py-1 text-xs text-gray-800 dark:text-gray-200">
                        {allFeatures.map((f) => {
                          const fId = f.localId || f.backendId;
                          return (
                            <div
                              key={fId}
                              onClick={() => {
                                setSelectedFeatureId(fId);
                                setIsFeatureDropdownOpen(false);
                              }}
                              className={`px-3 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer transition-colors truncate ${
                                selectedFeatureId === fId
                                  ? "bg-blue-50/50 dark:bg-blue-900/10 font-bold"
                                  : ""
                              }`}
                            >
                              {f.name} ({f.type})
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </div>
              );
            })()}
          </div>
        </div>
      </div>

      {/* Keyword filter */}
      <div className="space-y-1.5">
        <label className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
          Keywords
        </label>
        <input
          type="text"
          value={keywords}
          onChange={(e) => {
            const val = e.target.value;
            const commas = (val.match(/,/g) || []).length;
            if (commas > 4) {
              return;
            }
            const segments = val.split(",");
            const hasOverLongSegment = segments.some((s) => s.length > 20);
            if (hasOverLongSegment) {
              return;
            }
            setKeywords(val);
          }}
          placeholder="flood, hurricane, road closure (comma-separated)"
          className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-gray-800 dark:text-white outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400 transition placeholder:text-gray-300 dark:placeholder:text-gray-600"
        />
      </div>

      {/* Dates */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
            <Calendar size={12} className="text-gray-400" />
            Start Date
          </label>
          <input
            type="date"
            value={startDate}
            max={todayStr}
            onChange={(e) => {
              const val = e.target.value;
              if (val && val > todayStr) {
                setStartDate(todayStr);
              } else {
                setStartDate(val);
              }
            }}
            className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-gray-800 dark:text-white outline-none focus:border-blue-400 transition"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1">
            <Calendar size={12} className="text-gray-400" />
            End Date
          </label>
          <input
            type="date"
            value={endDate}
            max={todayStr}
            onChange={(e) => {
              const val = e.target.value;
              if (val && val > todayStr) {
                setEndDate(todayStr);
              } else {
                setEndDate(val);
              }
            }}
            className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-gray-800 dark:text-white outline-none focus:border-blue-400 transition"
          />
        </div>
      </div>

      {/* Advanced configurations */}
      <div className="space-y-3 p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-150 dark:border-gray-700 shadow-sm">
        <div className="flex items-center gap-1.5 text-xs font-bold text-gray-600 dark:text-gray-300">
          <Sliders size={13} className="text-gray-400" />
          <span>Search Parameters</span>
          <div className="relative group flex items-center">
            <Info
              size={13}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 cursor-help"
            />
            <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 text-[10px] rounded-lg border border-gray-200 dark:border-gray-700 shadow-md opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none text-center font-normal z-50">
              Select the number of results you want
            </span>
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wide font-bold">
            Max Results
          </label>
          <input
            type="number"
            min={1}
            max={50}
            value={maxResults}
            onKeyDown={(e) => {
              const allowedKeys = [
                "Backspace",
                "Delete",
                "Tab",
                "ArrowLeft",
                "ArrowRight",
                "ArrowUp",
                "ArrowDown",
                "Enter",
              ];
              if (!allowedKeys.includes(e.key) && !/^\d$/.test(e.key)) {
                e.preventDefault();
              }
            }}
            onChange={(e) => {
              const val = e.target.value.replace(/\D/g, "");
              if (val === "") {
                setMaxResults("");
              } else {
                const num = parseInt(val, 10);
                if (!isNaN(num)) {
                  setMaxResults(Math.min(50, Math.max(1, num)));
                }
              }
            }}
            className="w-full text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-gray-800 dark:text-white outline-none focus:border-blue-400 transition"
          />
        </div>
      </div>

      {/* Submit button */}
      <button
        type="submit"
        disabled={loading || allFeatures.length === 0}
        className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold py-2.5 px-4 rounded-xl shadow-lg transition disabled:opacity-40 disabled:cursor-not-allowed text-xs"
      >
        {loading ? "Searching News..." : "Search News"}
      </button>
    </form>
  );
}
