// src/hooks/useMap.js
import { useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { setBasemap, setViewport, setMeasuring, setActiveTool, setMapInstance } from '@/state/mapSlice.js';
import { MAP_PROVIDERS, DEFAULT_BASEMAP } from '@/config/apiConfig.js';

export function useMap() {
  const dispatch = useDispatch();

  const basemapId    = useSelector((state) => state.map.basemap);
  const center       = useSelector((state) => state.map.center);
  const zoom         = useSelector((state) => state.map.zoom);
  const activeTool   = useSelector((state) => state.map.activeTool);
  const mapInstance  = useSelector((state) => state.map.mapInstance);

  const activeProvider = MAP_PROVIDERS[basemapId] || MAP_PROVIDERS[DEFAULT_BASEMAP];

  const changeBasemap = useCallback(
    (id) => dispatch(setBasemap(id)),
    [dispatch]
  );

  const flyTo = useCallback(
    (nextCenter, nextZoom) => dispatch(setViewport({ center: nextCenter, zoom: nextZoom })),
    [dispatch]
  );

  const toggleMeasuring = useCallback(
    (value) => dispatch(setMeasuring(value)),
    [dispatch]
  );

  const changeActiveTool = useCallback(
    (tool) => dispatch(setActiveTool(tool)),
    [dispatch]
  );

  const registerMapInstance = useCallback(
    (instance) => dispatch(setMapInstance(instance)),
    [dispatch]
  );

  const zoomIn = useCallback(() => {
    if (mapInstance) {
      mapInstance.zoomIn();
      dispatch(setViewport({ zoom: mapInstance.getZoom() + 1 }));
    }
  }, [mapInstance, dispatch]);

  const zoomOut = useCallback(() => {
    if (mapInstance) {
      mapInstance.zoomOut();
      dispatch(setViewport({ zoom: mapInstance.getZoom() - 1 }));
    }
  }, [mapInstance, dispatch]);

  return {
    basemapId,
    activeProvider,
    center,
    zoom,
    activeTool,
    mapInstance,
    changeBasemap,
    flyTo,
    toggleMeasuring,
    changeActiveTool,
    registerMapInstance,
    zoomIn,
    zoomOut,
  };
}
