import { useState } from "react";
import { useSelector, useDispatch } from "react-redux";
import { openCommentModal } from "@/state/drawingSlice.js";
import toast from "react-hot-toast";
import {
  MousePointer2,
  Pencil,
  Type,
  Bookmark,
  MessageSquare,
  Undo2,
  Redo2,
  Hexagon,
  MapPin,
  Circle,
  Square,
  Lasso,
  Minus,
  Plus,
  Ruler,
} from "lucide-react";
import IconButton from "../iconButton/IconButton";
import ToolDropdown from "../toolDropdown/ToolDropdown.jsx";

const Divider = () => <div className="w-px h-6 bg-gray-200 mx-1" />;

const SELECT_OPTIONS = [
  { id: "lasso", label: "Lasso Select", icon: Lasso },
  { id: "rect-sel", label: "Rectangle Select", icon: Square },
  { id: "poly-sel", label: "Polygon Select", icon: Hexagon },
];

const DRAW_OPTIONS = [
  { id: "polygon", label: "Polygon", icon: Hexagon },
  { id: "polyline", label: "Line", icon: Minus }, // ← was "line", now "polyline" to match DrawingManager
  { id: "point", label: "Point", icon: MapPin },
  { id: "circle", label: "Circle", icon: Circle },
  { id: "rectangle", label: "Rectangle", icon: Square },
];

export default function BottomToolbar({ activeTool, setActiveTool, onZoomIn, onZoomOut }) {
  const [openDropdown, setOpenDropdown] = useState(null);
  const dispatch = useDispatch();
  const selectedFeatureId = useSelector((s) => s.layers.selectedFeatureId);
  const items = useSelector((s) => s.layers.items);

  const selectActive = ["select", ...SELECT_OPTIONS.map((o) => o.id)].includes(
    activeTool,
  );
  const drawActive = [...DRAW_OPTIONS.map((o) => o.id)].includes(activeTool);

  const toggleDropdown = (key) => {
    setOpenDropdown((prev) => (prev === key ? null : key));
  };

  const pick = (id) => {
    setActiveTool(id); // ← writes to Redux
    setOpenDropdown(null);
  };

  return (
    <div 
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => e.stopPropagation()}
      className="flex items-center gap-1 bg-white/90 dark:bg-gray-900/90 backdrop-blur rounded-2xl shadow-lg border border-gray-100 dark:border-gray-800 px-2 py-2"
    >
      <div className="relative">
        <IconButton
          label="Select"
          active={openDropdown ? openDropdown === "select" : selectActive}
          onClick={() => {
            pick("select");
            toggleDropdown("select");
          }}
        >
          <MousePointer2 size={16} />
        </IconButton>
        {openDropdown === "select" && (
          <ToolDropdown
            options={SELECT_OPTIONS}
            onSelect={pick}
            onClose={() => setOpenDropdown(null)}
          />
        )}
      </div>

      <div className="relative">
        <IconButton
          label="Draw"
          active={openDropdown ? openDropdown === "draw" : drawActive}
          onClick={() => toggleDropdown("draw")}
        >
          <Pencil size={16} />
        </IconButton>
        {openDropdown === "draw" && (
          <ToolDropdown
            options={DRAW_OPTIONS}
            onSelect={pick}
            onClose={() => setOpenDropdown(null)}
          />
        )}
      </div>

      {/* <IconButton
        label="Text"
        active={activeTool === "text"}
        onClick={() => pick("text")}
      >
        <Type size={16} />
      </IconButton> */}
      {/* <IconButton
        label="Bookmark"
        active={activeTool === "bookmark"}
        onClick={() => pick("bookmark")}
      >
        <Bookmark size={16} />
      </IconButton> */}
      <IconButton
        label="Comment"
        active={openDropdown ? false : activeTool === "comment"}
        onClick={() => {
          if (activeTool === "comment") {
            pick("select");
            return;
          }
          if (selectedFeatureId) {
            const allFeatures = items.flatMap((l) => l.features || []);
            const feature = allFeatures.find(
              (f) => f.backendId === selectedFeatureId || f.localId === selectedFeatureId
            );
            if (feature) {
              dispatch(openCommentModal(feature.backendId || feature.localId));
              return;
            }
          }
          pick("comment");
        }}
      >
        <MessageSquare size={16} />
      </IconButton>

      <Divider />

      <IconButton
        label="Measure"
        active={openDropdown ? false : activeTool === "measure"}
        onClick={() => pick(activeTool === "measure" ? "select" : "measure")}
      >
        <Ruler size={16} />
      </IconButton>
      <IconButton label="Zoom in" onClick={onZoomIn}>
        <Plus size={16} />
      </IconButton>
      <IconButton label="Zoom out" onClick={onZoomOut}>
        <Minus size={16} />
      </IconButton>
    </div>
  );
}
