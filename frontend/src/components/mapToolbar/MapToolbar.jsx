// src/components/mapToolbar/MapToolbar.jsx
import { useState, useRef } from "react";
import L from "leaflet";
import { Layers } from "lucide-react";
import IconButton from "../iconButton/IconButton";
import BasemapPicker, { BASEMAP_OPTIONS } from "../basemappicker/Basemappicker";
import { useMap } from "@/hooks/useMap.js";
import LeftToolbar from "../leftToolbar/LeftToolbar.jsx";
import BottomToolbar from "../bottomToolbar/BottomToolbar.jsx";

export default function MapToolbar({
  sidebarOpen = true,
  sidebarWidth = 288,
  rightWidth = 288,
  headerHeight = 56,
}) {
  const [basemapOpen, setBasemapOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const searchTimeoutRef = useRef(null);
  const locateMarkerRef = useRef(null);

  // ← activeTool now comes from Redux, not local state
  const {
    basemapId,
    changeBasemap,
    activeTool,
    changeActiveTool,
    zoom,
    zoomIn,
    zoomOut,
    flyTo,
    mapInstance,
  } = useMap();

  const handleSearchToggle = () => {
    setSearchOpen((prev) => !prev);
    if (searchOpen) {
      setSearchQuery("");
      setSuggestions([]);
    }
  };

  const handleSearchInput = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);

    if (val.trim().length < 3) {
      setSuggestions([]);
      return;
    }

    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(val)}&addressdetails=1&limit=5&email=test@example.com`,
        );
        const data = await res.json();
        setSuggestions(data.slice(0, 5));
      } catch (err) {
        console.error(err);
      }
    }, 400);
  };

  const selectSuggestion = (item) => {
    flyTo([parseFloat(item.lat), parseFloat(item.lon)], 14);
    setSearchOpen(false);
    setSearchQuery("");
    setSuggestions([]);
  };

  const handleLocate = () => {
    if (mapInstance) {
      mapInstance.locate({ setView: true, maxZoom: 16 });
      mapInstance.once("locationfound", (e) => {
        flyTo([e.latlng.lat, e.latlng.lng], mapInstance.getZoom());

        if (locateMarkerRef.current) {
          mapInstance.removeLayer(locateMarkerRef.current);
        }

        locateMarkerRef.current = L.circleMarker(e.latlng, {
          radius: 8,
          color: "#ffffff",
          weight: 2,
          fillColor: "#3b82f6",
          fillOpacity: 1,
        }).addTo(mapInstance);
      });
    }
  };

  const handleMeasure = () => {
    changeActiveTool(activeTool === "measure" ? "select" : "measure");
  };

  const leftEdge = (sidebarOpen ? sidebarWidth : 0) + 16;
  const centerOffset = ((sidebarOpen ? sidebarWidth : 0) - rightWidth) / 2;

  return (
    <>
      <div
        className="fixed transition-all duration-300 ease-in-out z-[1000] flex gap-3"
        style={{ top: headerHeight + 16, left: leftEdge }}
      >
        <LeftToolbar
          zoom={zoom}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
          onSearchToggle={handleSearchToggle}
          searchOpen={searchOpen}
          onLocate={handleLocate}
          onMeasure={handleMeasure}
          activeTool={activeTool}
        />
        {searchOpen && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 p-3 w-72 flex flex-col gap-2 h-fit">
            <input
              type="text"
              autoFocus
              placeholder="Search location..."
              value={searchQuery}
              onChange={handleSearchInput}
              className="w-full rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 dark:text-white px-3 py-2 text-sm outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition"
            />
            {suggestions.length > 0 && (
              <div className="flex flex-col gap-1 mt-1 max-h-60 overflow-y-auto">
                {suggestions.map((item) => (
                  <button
                    key={item.place_id}
                    onClick={() => selectSuggestion(item)}
                    className="text-left text-sm text-gray-700 hover:bg-blue-50 hover:text-blue-600 px-3 py-2 rounded-xl transition"
                  >
                    {item.display_name}
                  </button>
                ))}
              </div>
            )}
            {searchQuery.length >= 3 && suggestions.length === 0 && (
              <div className="text-sm text-gray-400 px-3 py-2">
                No results found.
              </div>
            )}
          </div>
        )}
      </div>

      <div
        className="fixed transition-all duration-300 ease-in-out z-[1000]"
        style={{ bottom: 16, left: leftEdge }}
      >
        {basemapOpen && (
          <>
            {/* Invisible backdrop that closes the popup when you click away */}
            <div
              className="fixed inset-0 z-[1050]"
              onClick={() => setBasemapOpen(false)}
            />

            <div className="absolute bottom-full left-0 mb-2 z-[1100]">
              <BasemapPicker
                options={BASEMAP_OPTIONS}
                selected={basemapId}
                onSelect={(id) => {
                  changeBasemap(id);
                  setBasemapOpen(false);
                }}
                onClose={() => setBasemapOpen(false)}
              />
            </div>
          </>
        )}
        <IconButton
          label="Basemap"
          active={basemapOpen}
          onClick={() => setBasemapOpen((v) => !v)}
        >
          <Layers size={16} />
        </IconButton>
      </div>

      <div
        className="fixed bottom-4 transition-all duration-300 ease-in-out z-[1000]"
        style={{
          left: `calc(50% + ${centerOffset}px)`,
          transform: "translateX(-50%)",
        }}
      >
        <BottomToolbar
          activeTool={activeTool}
          setActiveTool={changeActiveTool}
          onZoomIn={zoomIn}
          onZoomOut={zoomOut}
        />
      </div>
    </>
  );
}