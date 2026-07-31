/**
 * Reusable icon button with a built-in hover tooltip.
 * Used across the whole dashboard (MapToolbar, LeftSidebar, RightSidebar,
 * Header) so every button shares identical size, hover, press, focus, and
 * tooltip behavior.
 *
 * Default size is "sm" (36px) — the dashboard-wide standard.
 * Only override `size` for a genuinely special case.
 *
 * Usage:
 *   <IconButton label="Search"><Search size={16} /></IconButton>
 *   <IconButton label="Select" active><MousePointer2 size={16} /></IconButton>
 */
export default function IconButton({
  children,
  label,
  active = false,
  disabled = false,
  variant = "solid", // "solid" | "ghost"
  size = "sm", // "sm" (36px) | "md" (40px) | "lg" (44px)
  tooltipPosition = "top", // "top" | "bottom" | "left" | "right"
  className = "",
  ...props
}) {
  const sizeMap = {
    sm: "w-9 h-9", // 36px — dashboard default
    md: "w-10 h-10", // 40px
    lg: "w-11 h-11", // 44px — legacy/large size, avoid unless needed
  };

  const base = `
    ${sizeMap[size]}
    flex items-center justify-center shrink-0 rounded-xl
    transition-all duration-150 ease-out
    active:scale-90
    focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-1
    disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100
  `;

  const variantMap = {
    solid: active
      ? "bg-blue-600 text-white shadow-sm hover:bg-blue-700"
      : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 shadow-sm hover:bg-gray-100 dark:hover:bg-gray-700",
    ghost: active
      ? "bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400"
      : "bg-transparent text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800",
  };

  const tooltipPositionMap = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <div className="relative group inline-flex">
      <button
        type="button"
        disabled={disabled}
        className={`${base} ${variantMap[variant]} ${className}`}
        {...props}
      >
        {children}
      </button>

      {label && (
        <span
          role="tooltip"
          className={`
            pointer-events-none absolute z-40 whitespace-nowrap
            rounded-md bg-gray-900 px-2 py-1 text-xs font-medium text-white
            opacity-0 scale-95 transition-all duration-150
            group-hover:opacity-100 group-hover:scale-100
            ${tooltipPositionMap[tooltipPosition]}
          `}
        >
          {label}
        </span>
      )}
    </div>
  );
}