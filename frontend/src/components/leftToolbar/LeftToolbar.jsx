import { Search, Ruler, Camera, LocateFixed, Plus, Minus } from "lucide-react";
import IconButton from "../iconButton/IconButton";

export default function LeftToolbar({
  zoom,
  onZoomIn,
  onZoomOut,
  onSearchToggle,
  searchOpen,
  onMeasure,
  onLocate,
  activeTool,
}) {
  return (
    <div className="">
      {/* <IconButton
        label="Search"
        tooltipPosition="right"
        active={searchOpen}
        onClick={onSearchToggle}
      >
        <Search size={16} />
      </IconButton> */}
      {/* <IconButton
        label="Measure"
        tooltipPosition="right"
        active={activeTool === "measure"}
        onClick={onMeasure}
      >
        <Ruler size={16} />
      </IconButton> */}
      {/* <IconButton label="Snapshot" tooltipPosition="right">
        <Camera size={16} />
      </IconButton> */}
      {/* <div className="mt-1 flex flex-col items-center gap-1 border-t border-gray-100 pt-2">
        <IconButton label="Zoom in" tooltipPosition="right" onClick={onZoomIn}>
          <Plus size={16} />
        </IconButton>
        <IconButton
          label="Zoom out"
          tooltipPosition="right"
          onClick={onZoomOut}
        >
          <Minus size={16} />
        </IconButton>
      </div> */}
    </div>
  );
}
