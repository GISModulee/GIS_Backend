import { useState, useEffect } from "react";
import { useSelector, useDispatch } from "react-redux";
import { useNavigate } from "react-router-dom";
import { logout, setCases } from "@/state/authSlice.js";
import toast from "react-hot-toast";
import { Menu, ChevronDown, LogOut } from "lucide-react";
import IconButton from "../iconButton/IconButton";
import ThemeToggle from "../themeToggle/ThemeToggle";
import layerService from "@/utils/layerService.js";

const Header = ({ onToggleSidebar }) => {
  const activeCaseIdFromStore = useSelector((s) => s.auth.activeCaseId);
  const match = window.location.pathname.match(/\/map\/(\d+)/);
  const activeCaseId = match ? parseInt(match[1], 10) : activeCaseIdFromStore;

  const user = useSelector((s) => s.auth.user);
  const cases = useSelector((s) => s.auth.cases);
  const [projectName, setProjectName] = useState("Loading case...");
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);

  const navigate = useNavigate();
  const dispatch = useDispatch();

  const handleLogout = () => {
    dispatch(logout());
    toast.success("Logged out successfully");
    navigate("/login");
  };

  useEffect(() => {
    if (!activeCaseId) return;

    // Try to find the active case in our cached store list
    const activeCase = cases.find((c) => Number(c.id) === Number(activeCaseId));
    if (activeCase) {
      setProjectName(activeCase.title || activeCase.name || `Case ${activeCaseId}`);
    } else {
      let isMounted = true;
      const fetchSingleCase = async () => {
        try {
          const res = await layerService.getCaseById(activeCaseId);
          if (isMounted && res) {
            setProjectName(res.title || res.name || `Case ${activeCaseId}`);
          }
        } catch (err) {
          console.error("Failed to load case name:", err);
          if (isMounted) {
            setProjectName(`Case ${activeCaseId}`);
          }
        }
      };
      fetchSingleCase();
      return () => { isMounted = false; };
    }
  }, [activeCaseId, cases]);

  return (
    <header className="relative z-[1020] w-full h-14 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center px-4 gap-4 shadow-sm">
      {/* Left — Hamburger + Project Title */}
      <div className="flex items-center gap-3 min-w-[200px]">
        <IconButton
          size="sm"
          variant="ghost"
          label="Toggle sidebar"
          onClick={onToggleSidebar}
        >
          <Menu size={16} />
        </IconButton>

        <span className="font-semibold text-gray-800 dark:text-gray-100 text-sm whitespace-nowrap">
          {projectName}
        </span>
      </div>

      {/* Center — Spacer */}
      <div className="flex-1" />

      {/* Right — Dark toggle, Avatar */}
      <div className="flex items-center gap-2 min-w-[140px] justify-end">
        <ThemeToggle />

        <div className="relative">
          <div
            onClick={() => setIsUserDropdownOpen(!isUserDropdownOpen)}
            className="flex items-center gap-1 cursor-pointer"
            title={user?.email || "User"}
          >
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
              {user?.email ? user.email.charAt(0).toUpperCase() : "U"}
            </div>
            <ChevronDown size={12} className="text-gray-400" />
          </div>

          {isUserDropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg p-1 z-50 animate-in fade-in slide-in-from-top-1 duration-100">
              <div className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700 truncate font-medium">
                {user?.email || "User Profile"}
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-3 py-2 mt-1 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
              >
                <LogOut size={14} />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;