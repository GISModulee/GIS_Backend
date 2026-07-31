// src/components/BasemapSwitcher/BasemapSwitcher.jsx
import { useState } from 'react';
import { Layers, X } from 'lucide-react';
import clsx from 'clsx';
import { useMap } from '@/hooks/useMap.js';
import { MAP_PROVIDERS } from '@/config/apiConfig.js';

// A floating panel anchored to the bottom-left of the map.
// State split:
//   - isOpen   → local (only this component needs to know if panel is visible)
//   - basemapId → Redux (MapView and other components also need to react to it)
export default function BasemapSwitcher() {
  const [isOpen, setIsOpen] = useState(false);
  const { basemapId, changeBasemap } = useMap();

  const handleSelect = (id) => {
    changeBasemap(id);   // → dispatches setBasemap → saves to localStorage
    setIsOpen(false);    // close the panel after selection
  };

  return (
    // z-[400] keeps it above the Leaflet map tiles (z-index ~200-300)
    <div className="absolute bottom-20 left-4 z-[400]">

      {/* Trigger button — the blue layers icon at the bottom left */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg hover:bg-brand-700 transition-colors"
        title="Change basemap"
      >
        <Layers size={20} />
      </button>

      {/* Panel — only rendered when open */}
      {isOpen && (
        <div className="absolute bottom-14 left-0 w-64 rounded-2xl bg-white shadow-2xl border border-gray-100 dark:bg-gray-900 dark:border-gray-800 p-4">

          {/* Panel header */}
          <div className="flex items-center justify-between mb-4">
            <span className="font-semibold text-gray-900 dark:text-gray-100">Basemap</span>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <X size={16} />
            </button>
          </div>

          {/* 2-column grid of basemap cards */}
          <div className="grid grid-cols-2 gap-3">
            {Object.values(MAP_PROVIDERS).map((provider) => {
              const isActive = provider.id === basemapId;

              return (
                <button
                  key={provider.id}
                  onClick={() => handleSelect(provider.id)}
                  className={clsx(
                    'flex flex-col items-center gap-2 rounded-xl p-2 border-2 transition-all',
                    isActive
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-600/10'
                      : 'border-transparent hover:border-gray-200 dark:hover:border-gray-700'
                  )}
                >
                  {/* Color swatch — uses the `color` field from MAP_PROVIDERS */}
                  <div
                    className="w-full h-12 rounded-lg"
                    style={{ backgroundColor: provider.color }}
                  />

                  {/* Label */}
                  <span
                    className={clsx(
                      'text-xs font-medium text-center leading-tight',
                      isActive
                        ? 'text-brand-700 dark:text-brand-400'
                        : 'text-gray-600 dark:text-gray-300'
                    )}
                  >
                    {provider.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
