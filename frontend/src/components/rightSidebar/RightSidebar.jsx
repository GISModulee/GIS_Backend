import { useState } from "react";
import { useSelector } from "react-redux";
import { Plus, Send } from "lucide-react";
import IconButton from "../iconButton/IconButton";

const RobotIcon = ({ size = 20, className = "" }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
    <line x1="8" y1="16" x2="8" y2="16" strokeWidth={3} />
    <line x1="16" y1="16" x2="16" y2="16" strokeWidth={3} />
    <path d="M8 11V9a4 4 0 018 0v2" />
  </svg>
);

const Tab = ({ label, active, onClick }) => (
  <button
    onClick={onClick}
    className={`flex-1 py-2 rounded-full text-sm font-semibold transition ${
      active
        ? "bg-blue-600 text-white"
        : "bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
    }`}
  >
    {label}
  </button>
);

const EmptyChat = () => {
  const user = useSelector((s) => s.auth.user);
  const rawUsername = user?.username || user?.name || (user?.email ? user.email.split("@")[0] : null) || "User";
  const username = rawUsername.charAt(0).toUpperCase() + rawUsername.slice(1);

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3">
      <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center">
        <RobotIcon size={32} className="text-blue-500" />
      </div>
      <div className="text-center">
        <p className="text-xl font-bold text-gray-900 dark:text-white">
          Hey <span className="text-blue-600">{username}</span> 👋
        </p>
        <p className="text-sm text-gray-455 dark:text-gray-400 mt-1">Ask me about your data.</p>
      </div>
    </div>
  );
};

const EmptyHistory = () => (
  <div className="flex-1 flex flex-col items-center justify-center gap-2">
    <svg
      className="w-10 h-10 text-gray-350 dark:text-gray-600"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
    <p className="text-sm text-gray-400">No chat history yet.</p>
  </div>
);

export default function RightSidebar({ className = "fixed top-14 right-0 h-[calc(100vh-56px)]" }) {
  const [activeTab, setActiveTab] = useState("chat");
  const [input, setInput] = useState("");

  return (
    <aside className={`${className} w-72 bg-gray-50 dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 z-[1010] flex flex-col`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-4">
        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
          <RobotIcon size={20} className="text-blue-600" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-bold text-gray-900 dark:text-white">
            ChatBot
          </p>
          <p className="text-xs text-gray-400">Your Analytical AI Bot</p>
        </div>
        <IconButton
          size="sm"
          variant="ghost"
          label="New chat"
          className="!bg-white dark:!bg-gray-800 !shadow-sm border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200"
        >
          <Plus size={16} />
        </IconButton>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 px-4 pb-3">
        <Tab
          label="Current Chat"
          active={activeTab === "chat"}
          onClick={() => setActiveTab("chat")}
        />
        <Tab
          label="History"
          active={activeTab === "history"}
          onClick={() => setActiveTab("history")}
        />
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-2 flex flex-col">
        {activeTab === "chat" ? <EmptyChat /> : <EmptyHistory />}
      </div>

      {/* Input */}
      <div className="p-4">
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Ask anything..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="flex-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 dark:text-white rounded-full px-4 py-2.5 text-sm outline-none placeholder-gray-400 focus:border-blue-400 transition"
          />
          <IconButton
            size="sm"
            label="Send"
            active={!!input.trim()}
            disabled={!input.trim()}
          >
            <Send size={16} />
          </IconButton>
        </div>
      </div>
    </aside>
  );
}