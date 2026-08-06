import { useState, useEffect } from "react";
import { useSelector, useDispatch } from "react-redux";
import Header from "../header/Header";
import LeftSidebar from "../leftSidebar/LeftSidebar";
import RightSidebar from "../rightSidebar/RightSidebar";
import MapToolbar from "../mapToolbar/MapToolbar";
import MapView from "../mapView/MapView";
import SaveShapeModal from "../saveShapeModal/SaveShapeModal.jsx";
import { clearPendingGeometry } from "../../state/layersSlice.js";
import DrawingManager from "../drawingManager/DrawingManager.jsx";
import { useLayers } from "../../hooks/useLayers.js";
import CommentModal from "../commentModal/CommentModal.jsx";
import DeleteConfirmModal from "../deleteConfirmModal/DeleteConfirmModal.jsx";
import { useNavigate, useParams } from "react-router-dom";
import { setActiveCase } from "../../state/authSlice.js";

const SIDEBAR_WIDTH = 288;
const RIGHT_WIDTH = 288;
const HEADER_HEIGHT = 56;

// ── Modal controller ──────────────────────────────────────
function ModalController() {
  const dispatch = useDispatch();
  const pendingGeometry = useSelector((s) => s.layers.pendingGeometry);
  const pendingType = useSelector((s) => s.layers.pendingType);
  const { saveShape } = useLayers();

  if (!pendingGeometry) return null;

  const handleSave = async ({ name, category, color }) => {
    await saveShape({ name, category, color });
  };

  const handleCancel = () => {
    DrawingManager.clearTempLayer?.();
    dispatch(clearPendingGeometry());
  };

  return (
    <SaveShapeModal
      type={pendingType}
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
}

import { ACTIVE_CASE_ID } from "../../config/apiConfig.js";

export default function MapWorkspace() {
  const { caseId } = useParams();
  const dispatch = useDispatch();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { loadLayersFromBackend } = useLayers();
  const navigate = useNavigate();
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const [mapLoading, setMapLoading] = useState(false);

  useEffect(() => {
    const checkCaseSelection = () => {
      if (!caseId) {
        if (activeCaseIdFromStore) {
          navigate(`/map/${activeCaseIdFromStore}`, { replace: true });
        } else {
          dispatch(setActiveCase(ACTIVE_CASE_ID));
          navigate(`/map/${ACTIVE_CASE_ID}`, { replace: true });
        }
      }
    };
    checkCaseSelection();
  }, [caseId, activeCaseIdFromStore, dispatch, navigate]);

  useEffect(() => {
    if (caseId) {
      const parsedId = parseInt(caseId, 10);
      if (!isNaN(parsedId)) {
        dispatch(setActiveCase(parsedId));
      }
    }
  }, [caseId, dispatch]);

  // Load all layers + features from backend once on mount
  useEffect(() => {
    if (caseId) {
      console.log("get api for layers");
      setMapLoading(true);
      loadLayersFromBackend()
        .catch((err) => {
          console.error("Failed to load case data:", err);
        })
        .finally(() => {
          setMapLoading(false);
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header onToggleSidebar={() => setSidebarOpen((p) => !p)} />
      <div
        className="relative flex-1"
        style={{
          marginLeft: 0,
          marginRight: RIGHT_WIDTH,
        }}
      >
        <MapView sidebarOpen={sidebarOpen} />
        <MapToolbar
          sidebarOpen={sidebarOpen}
          sidebarWidth={SIDEBAR_WIDTH}
          rightWidth={RIGHT_WIDTH}
          headerHeight={HEADER_HEIGHT}
        />
        {mapLoading && (
          <div className="absolute inset-0 bg-white/40 dark:bg-gray-950/40 backdrop-blur-[2px] z-[1500] flex flex-col items-center justify-center gap-3">
            <div className="animate-spin rounded-full h-10 w-10 border-4 border-blue-100 border-t-blue-600 dark:border-blue-900/40 dark:border-t-blue-500"></div>
            <span className="text-xs font-semibold text-gray-700 dark:text-gray-200 animate-pulse">Loading map data...</span>
          </div>
        )}
      </div>
      <LeftSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <RightSidebar />
      <ModalController />
      <CommentModal />
      <DeleteConfirmModal />
    </div>
  );
}
