import { useRef, useEffect } from "react";

export default function ToolDropdown({ options, onSelect, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 p-2 min-w-[165px] z-[1100]"
    >
      {options.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          onClick={() => {
            onSelect(id);
            onClose();
          }}
          className="flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-blue-50 dark:hover:bg-gray-700 hover:text-blue-600 transition-colors"
        >
          {Icon && <Icon size={15} className="shrink-0" />}
          {label}
        </button>
      ))}
    </div>
  );
}
