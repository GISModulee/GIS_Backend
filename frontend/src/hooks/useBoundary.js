import { useState, useEffect, useCallback } from "react";
import boundaryService from "@/utils/boundaryService.js";
 
export function useBoundary() {
  const [geojson, setGeojson] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [attribution, setAttribution] = useState(null);
 
  const fetchBoundary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await boundaryService.getIndiaBoundary();
      setGeojson(data.boundary);
      setAttribution(data.attribution);
    } catch (err) {
      console.error("[useBoundary] fetch error:", err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);
 
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBoundary();
  }, [fetchBoundary]);
 
  return { geojson, loading, error, attribution, refetch: fetchBoundary };
}