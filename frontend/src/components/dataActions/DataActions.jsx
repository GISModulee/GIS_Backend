import { useState } from "react";
import { useDispatch } from "react-redux";
import { setActiveVectorOp } from "@/state/layersSlice.js";
import { ChevronDown, ChevronRight, HelpCircle } from "lucide-react";
import UnionAction from "../unionAction/UnionAction.jsx";
import IntersectionAction from "../intersectionAction/IntersectionAction.jsx";
import DifferenceAction from "../differenceAction/DifferenceAction.jsx";
import BufferAction from "../bufferAction/BufferAction.jsx";
import CentroidAction from "../centroidAction/CentroidAction.jsx";
import ConvexHullAction from "../convexHullAction/ConvexHullAction.jsx";
import SymmetricDifferenceAction from "../symmetricDifferenceAction/SymmetricDifferenceAction.jsx";

export default function DataActions() {
  const dispatch = useDispatch();
  const [isOpen, setIsOpen] = useState(false);
  const [activeOp, setActiveOp] = useState(null);

  // SVG Icons for Vector Operations
  const icons = {
    vectorOps: (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
        <path d="M7.5 10.5c.828 0 1.5-.672 1.5-1.5s-.672-1.5-1.5-1.5-1.5.672-1.5 1.5.672 1.5 1.5 1.5z" />
        <path d="M11.5 16.5c.828 0 1.5-.672 1.5-1.5s-.672-1.5-1.5-1.5-1.5.672-1.5 1.5.672 1.5 1.5 1.5z" />
        <path d="M16.5 11.5c.828 0 1.5-.672 1.5-1.5s-.672-1.5-1.5-1.5-1.5.672-1.5 1.5.672 1.5 1.5 1.5z" />
        <path d="M6 12h12M12 6v12" strokeDasharray="1.5 1.5" />
      </svg>
    ),
    intersection: (
      <svg className="w-[18px] h-[18px] text-blue-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left Circle outline */}
        <circle cx="9.5" cy="12" r="6" stroke="currentColor" strokeWidth="1.5" />
        {/* Right Circle outline */}
        <circle cx="14.5" cy="12" r="6" stroke="currentColor" strokeWidth="1.5" />
        {/* Intersected region (using a clip path or path) */}
        <path d="M12 7.15a6 6 0 0 1 2.5 4.85 6 6 0 0 1-2.5 4.85 6 6 0 0 1-2.5-4.85 6 6 0 0 1 2.5-4.85z" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
    union: (
      <svg className="w-[18px] h-[18px] text-indigo-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Entire merged shape path filled */}
        <path d="M9.5 6a6 6 0 0 0-4.24 10.24A6 6 0 0 0 9.5 18a5.97 5.97 0 0 0 2.5-.55 5.97 5.97 0 0 0 2.5.55 6 6 0 0 0 4.24-1.76A6 6 0 0 0 14.5 6a5.97 5.97 0 0 0-2.5.55A5.97 5.97 0 0 0 9.5 6z" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        {/* Shading/dashed line to indicate overlap inner boundary */}
        <path d="M12 7.15a6 6 0 0 1 0 9.7M12 7.15a6 6 0 0 0 0 9.7" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" />
      </svg>
    ),
    difference: (
      <svg className="w-[18px] h-[18px] text-red-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left Circle: Filled but excluding the overlap */}
        <path d="M9.5 6a6 6 0 0 0-6 6 6 6 0 0 0 6 6 5.97 5.97 0 0 0 2.5-.55A6 6 0 0 1 9.5 12a6 6 0 0 1 2.5-5.45A5.97 5.97 0 0 0 9.5 6z" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" />
        {/* Right Circle: Outline only */}
        <circle cx="14.5" cy="12" r="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 3" />
      </svg>
    ),
    buffer: (
      <svg className="w-[18px] h-[18px] text-emerald-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Inner solid circle */}
        <circle cx="12" cy="12" r="4.5" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" />
        {/* Outer buffer zone dashed circle */}
        <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 2" />
        {/* Radial lines representing buffer distance */}
        <path d="M12 3.5v4M12 16.5v4M3.5 12h4M16.5 12h4" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      </svg>
    ),
    symmetricDifference: (
      <svg className="w-[18px] h-[18px] text-purple-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left Circle: Outer part filled */}
        <path d="M9.5 6a6 6 0 0 0-6 6 6 6 0 0 0 6 6 5.97 5.97 0 0 0 2.5-.55A6 6 0 0 1 9.5 12a6 6 0 0 1 2.5-5.45A5.97 5.97 0 0 0 9.5 6z" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" />
        {/* Right Circle: Outer part filled */}
        <path d="M14.5 6a5.97 5.97 0 0 0-2.5.55A6 6 0 0 1 14.5 12a6 6 0 0 1-2.5 5.45 5.97 5.97 0 0 0 2.5.55 6 6 0 0 0 6-6 6 6 0 0 0-6-6z" fill="currentColor" fillOpacity="0.4" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
    centroid: (
      <svg className="w-[18px] h-[18px] text-pink-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Triangle outline */}
        <polygon points="12,4 4,18 20,18" stroke="currentColor" strokeWidth="1.5" fill="currentColor" fillOpacity="0.1" />
        {/* Center dot */}
        <circle cx="12" cy="13.5" r="2.5" fill="currentColor" stroke="currentColor" strokeWidth="1" />
      </svg>
    ),
    convexHull: (
      <svg className="w-[18px] h-[18px] text-amber-600" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Scatter points inside */}
        <circle cx="9" cy="9" r="1.5" fill="currentColor" />
        <circle cx="15" cy="11" r="1.5" fill="currentColor" />
        <circle cx="11" cy="15" r="1.5" fill="currentColor" />
        <circle cx="13" cy="7" r="1.5" fill="currentColor" />
        <circle cx="7" cy="13" r="1.5" fill="currentColor" />
        {/* Outer hull boundary */}
        <polygon points="13,5 17,10 13,17 6,14 8,7" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 2" fill="currentColor" fillOpacity="0.1" />
      </svg>
    ),
  };

  const vectorOperations = [
    {
      id: "intersection",
      name: "Intersection",
      description: "Extract the overlapping area common to both layers.",
      icon: icons.intersection,
    },
    {
      id: "union",
      name: "Union",
      description: "Combine all features from both layers into a single layer.",
      icon: icons.union,
    },
    {
      id: "difference",
      name: "Difference",
      description: "Keep areas in the input layer that do not overlap with the overlay.",
      icon: icons.difference,
    },
    {
      id: "buffer",
      name: "Buffer",
      description: "Create a zone of specified distance around input features.",
      icon: icons.buffer,
    },
    {
      id: "symmetricDifference",
      name: "Symmetric Difference",
      description: "Get areas that are in either feature but not in both.",
      icon: icons.symmetricDifference,
    },
    {
      id: "centroid",
      name: "Centroid",
      description: "Find the geometric center of a feature.",
      icon: icons.centroid,
    },
    {
      id: "convexHull",
      name: "Convex Hull",
      description: "Compute the smallest convex polygon containing the feature.",
      icon: icons.convexHull,
    },
  ];

  const handleSelectOp = (opId) => {
    const nextOp = activeOp === opId ? null : opId;
    setActiveOp(nextOp);
    dispatch(setActiveVectorOp(nextOp));
  };

  return (
    <div className="space-y-3">
      {/* Title */}
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 px-1">
        Data Actions
      </h3>

      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm transition-colors duration-200 relative">
        {/* Header Toggle */}
        <button
          onClick={() => {
            const nextOpen = !isOpen;
            setIsOpen(nextOpen);
            if (!nextOpen) {
              setActiveOp(null);
              dispatch(setActiveVectorOp(null));
            }
          }}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400">
              {icons.vectorOps}
            </div>
            <span className="font-semibold text-gray-800 dark:text-gray-200">Vector operations</span>
          </div>
          {isOpen ? (
            <ChevronDown size={14} className="text-gray-400 dark:text-gray-500" />
          ) : (
            <ChevronRight size={14} className="text-gray-400 dark:text-gray-500" />
          )}
        </button>

        {/* Collapsible Content */}
        {isOpen && (
          <div className="border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50 p-3 space-y-2 animate-in slide-in-from-top-2 duration-200">
            <div className="grid grid-cols-4 gap-1.5 w-full">
              {vectorOperations.map((op) => {
                const isActive = activeOp === op.id;
                return (
                  <button
                    key={op.id}
                    onClick={() => handleSelectOp(op.id)}
                    className={`group relative flex items-center justify-center p-2 rounded-lg border transition-all duration-200
                      ${isActive
                        ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/20 shadow-sm"
                        : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-sm"
                      }`}
                  >
                    <div className="transform group-hover:scale-110 transition-transform duration-200">
                      {op.icon}
                    </div>

                    {/* Hover Tooltip */}
                    <div className="absolute bottom-full mb-1.5 hidden group-hover:flex flex-col items-center z-30 animate-in fade-in zoom-in-95 duration-100 pointer-events-none">
                      <span className="relative z-10 px-2 py-1 text-[10px] text-white whitespace-nowrap bg-gray-900 dark:bg-gray-800 rounded shadow-md font-semibold border border-gray-800 dark:border-gray-700">
                        {op.name}
                      </span>
                      <div className="w-1.5 h-1.5 -mt-1 rotate-45 bg-gray-900 dark:bg-gray-800 border-r border-b border-gray-800 dark:border-gray-700"></div>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Render selected operation sub-component */}
            {activeOp === "union" && (
              <UnionAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "intersection" && (
              <IntersectionAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "difference" && (
              <DifferenceAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "buffer" && (
              <BufferAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "symmetricDifference" && (
              <SymmetricDifferenceAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "centroid" && (
              <CentroidAction onCancel={() => setActiveOp(null)} />
            )}
            {activeOp === "convexHull" && (
              <ConvexHullAction onCancel={() => setActiveOp(null)} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
