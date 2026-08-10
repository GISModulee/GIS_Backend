import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSelector, useDispatch } from "react-redux";
import { logout } from "@/state/authSlice.js";
import toast from "react-hot-toast";
import {
  Layers,
  Search,
  ChevronDown,
  LogOut,
} from "lucide-react";
import ThemeToggle from "../themeToggle/ThemeToggle";
import RightSidebar from "../rightSidebar/RightSidebar";
import DashboardSidebar from "../dashboardSidebar/DashboardSidebar.jsx";
import layerService from "@/utils/layerService.js";

export default function Dashboard() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const user = useSelector((s) => s.auth.user);
  const [activeTab, setActiveTab] = useState("cases");
  const [searchQuery, setSearchQuery] = useState("");
  const [casesList, setCasesList] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);

  const handleLogout = () => {
    dispatch(logout());
    toast.success("Logged out successfully");
    navigate("/login");
  };

  useEffect(() => {
    async function fetchCases() {
      try {
        const data = await layerService.getCases();
        console.log("getCases response: ", data);
        let list = [];
        if (Array.isArray(data)) {
          list = data;
        } else if (data && Array.isArray(data.data)) {
          list = data.data;
        } else if (data && Array.isArray(data.cases)) {
          list = data.cases;
        }
        setCasesList(list);
      } catch (err) {
        console.error("Error fetching cases:", err);
      } finally {
        setIsLoading(false);
      }
    }
    fetchCases();
  }, []);

  const defaultThumbnail = "https://images.unsplash.com/photo-1524661135-423995f22d0b?w=600&auto=format&fit=crop&q=60&ixlib=rb-4.0.3";

  const filteredCases = casesList.filter((c) => {
    const term = searchQuery.toLowerCase();
    const title = (c.title || c.name || "").toLowerCase();
    const desc = (c.description || "").toLowerCase();
    return title.includes(term) || desc.includes(term);
  });

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 font-sans transition-colors">
      {/* Sidebar */}
      <DashboardSidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-white dark:bg-gray-900 transition-colors">
        {/* Top Navbar */}
        <header className="relative z-[1020] h-14 border-b border-gray-200 dark:border-gray-800 px-6 flex items-center justify-between flex-shrink-0">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white capitalize">{activeTab}</h2>

          {/* Filters and Search */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
              <span>All cases</span>
              <ChevronDown size={12} className="text-gray-400 dark:text-gray-500" />
            </div>
            <div className="flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
              <span>All creators</span>
              <ChevronDown size={12} className="text-gray-400 dark:text-gray-500" />
            </div>
            <div className="flex items-center gap-2 border border-gray-200 dark:border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
              <span>Last edited</span>
              <ChevronDown size={12} className="text-gray-400 dark:text-gray-500" />
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500" size={14} />
              <input
                type="text"
                placeholder="Search cases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-56 border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white rounded-lg pl-9 pr-4 py-1.5 text-xs outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
              />
            </div>

            {/* Theme Toggle in Header */}
            <ThemeToggle className="ml-2" />

            {/* User Dropdown */}
            <div className="relative ml-2">
              <div
                onClick={() => setIsUserDropdownOpen(!isUserDropdownOpen)}
                className="flex items-center gap-1 cursor-pointer"
                title={user?.email || "User"}
              >
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold shadow-sm">
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

        <div className="flex-1 flex overflow-hidden">
          {/* Dashboard Panels */}
          <div className="flex-1 overflow-y-auto p-8 space-y-8">
            {activeTab === "cases" && (
              <>
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center py-20 space-y-3">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Loading cases...</p>
                  </div>
                ) : filteredCases.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
                    <Layers size={48} className="text-gray-300 dark:text-gray-600" />
                    <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300">No cases found</h3>
                    <p className="text-xs text-gray-400 dark:text-gray-500 max-w-sm">
                      Create or import cases in the workspace, or check your search criteria.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
                      All cases
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                      {filteredCases.map((c) => (
                        <div
                          key={c.id}
                          onClick={() => navigate(`/map/${c.id}`)}
                          className="group border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden shadow-sm hover:shadow-md hover:border-gray-300 dark:hover:border-gray-500 cursor-pointer transition duration-200 bg-white dark:bg-gray-800"
                        >
                          {/* Image Preview Container */}
                          <div className="aspect-[1.8/1] relative bg-gray-100 dark:bg-gray-900 overflow-hidden">
                            <img
                              src={c.thumbnail || defaultThumbnail}
                              alt={c.title || c.name || "Untitled Case"}
                              className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                            />
                            {c.priority && (
                              <span className="absolute top-3 left-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-gray-200/55 dark:border-gray-700/55 text-[10px] font-semibold text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded-full shadow-sm flex items-center gap-1">
                                <span className={`w-1.5 h-1.5 rounded-full ${c.priority === "high" ? "bg-red-500" : "bg-blue-500"}`} />
                                <span className="capitalize">{c.priority}</span>
                              </span>
                            )}
                          </div>

                          {/* Info Footer */}
                          <div className="p-4 space-y-1">
                            <h4 className="font-semibold text-sm text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition line-clamp-1">
                              {c.title || c.name || "Untitled Case"}
                            </h4>
                            <p className="text-xs text-gray-400 dark:text-gray-500 line-clamp-2">
                              {c.description || "No description provided."}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {activeTab === "datasets" && (
              <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
                <Layers size={48} className="text-gray-300 dark:text-gray-600" />
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300">No team datasets loaded</h3>
                <p className="text-xs text-gray-400 dark:text-gray-500 max-w-sm">
                  Shared workspace data layers and datasets will appear here once registered by your team members.
                </p>
              </div>
            )}

            {activeTab === "settings" && (
              <div className="max-w-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm space-y-6">
                <h3 className="text-base font-bold text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-700 pb-3">Workspace Settings</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-3 items-center">
                    <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">Workspace Name</span>
                    <input
                      type="text"
                      disabled
                      value={user?.email
                        ? `${user.email.split("@")[0].charAt(0).toUpperCase()}${user.email.split("@")[0].slice(1)}'s workspace`
                        : "My workspace"}
                      className="col-span-2 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 text-xs bg-gray-50 dark:bg-gray-900 text-gray-500 dark:text-gray-400 cursor-not-allowed"
                    />
                  </div>
                  <div className="grid grid-cols-3 items-center">
                    <span className="text-xs font-semibold text-gray-500 dark:text-gray-400">Plan Status</span>
                    <span className="col-span-2 text-xs font-bold text-blue-600 dark:text-blue-400">Starter Plan</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Chatbot Right Sidebar */}
          <RightSidebar className="h-full flex-shrink-0 hidden lg:flex" />
        </div>
      </main>
    </div>
  );
}
