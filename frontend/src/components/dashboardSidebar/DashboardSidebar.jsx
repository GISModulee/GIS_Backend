import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useDispatch, useSelector } from "react-redux";
import { logout } from "@/state/authSlice.js";
import toast from "react-hot-toast";
import {
  Folder,
  Layers,
  Settings,
  Plus,
  ChevronDown,
  LogOut,
} from "lucide-react";

export default function DashboardSidebar({ activeTab, setActiveTab }) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const user = useSelector((s) => s.auth.user);

  const handleLogout = () => {
    dispatch(logout());
    toast.success("Logged out successfully");
    navigate("/login");
  };

  return (
    <aside className="w-64 border-r border-gray-200 dark:border-gray-800 flex flex-col justify-between bg-gray-50 dark:bg-gray-900 flex-shrink-0 transition-colors">
      <div className="p-4 space-y-6">
        {/* Logo / Title */}
        <div className="flex items-center gap-2 px-2 py-1">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
            G
          </div>
          <span className="font-bold text-xl tracking-tight text-gray-900 dark:text-white">GIS</span>
        </div>

        {/* Workspace Switcher */}
        <div className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-3 shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-green-500 text-white flex items-center justify-center font-semibold text-xs">
              {user?.email ? user.email.charAt(0).toUpperCase() : "W"}
            </div>
            <span className="text-xs font-semibold text-gray-700 dark:text-gray-200">
              {user?.email
                ? `${user.email.split("@")[0].charAt(0).toUpperCase()}${user.email.split("@")[0].slice(1)}'s workspace`
                : "My workspace"}
            </span>
          </div>
          <ChevronDown size={14} className="text-gray-400 dark:text-gray-500" />
        </div>

        {/* Navigation Links */}
        <nav className="space-y-1">
          <button
            onClick={() => setActiveTab("cases")}
            className={`flex w-full items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${activeTab === "cases"
              ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
              : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
          >
            <Folder size={16} />
            <span>Cases</span>
          </button>
          <button
            onClick={() => setActiveTab("datasets")}
            className={`flex w-full items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition ${activeTab === "datasets"
              ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
              : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
          >
            <div className="flex items-center gap-3">
              <Layers size={16} />
              <span>Datasets</span>
            </div>
            <span className="text-[10px] bg-orange-100 text-orange-600 px-2 py-0.5 rounded-full font-bold">
              Team
            </span>
          </button>
          <button
            onClick={() => setActiveTab("settings")}
            className={`flex w-full items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${activeTab === "settings"
              ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
              : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
          >
            <Settings size={16} />
            <span>Settings</span>
          </button>
        </nav>
      </div>
    </aside>
  );
}
