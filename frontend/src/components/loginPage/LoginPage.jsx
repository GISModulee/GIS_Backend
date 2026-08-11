import { useState, useEffect } from "react";
import { Mail, Lock, Eye, EyeOff, ArrowRight } from "lucide-react";
import { useNavigate, Link } from "react-router-dom";
import { useDispatch } from "react-redux";
import { setCredentials, logout } from "@/state/authSlice.js";
import { authService } from "@/utils/authService.js";
import toast from "react-hot-toast";
import loginBg from "@/assets/loginbg.jpeg";
import ThemeToggle from "../themeToggle/ThemeToggle";
import { getErrorMessage } from "@/utils/ErrorUtils.js";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const dispatch = useDispatch();

    useEffect(() => {
        dispatch(logout());
        if (sessionStorage.getItem("network_error_toast") === "true") {
            toast.error("Network Error", { id: "network-error" });
            sessionStorage.removeItem("network_error_toast");
        }
    }, [dispatch]);

    const handleLogin = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            // Call backend API
            const data = await authService.login(email, password);
            console.log("Full Login Data from backend: ", data);

            // If backend returned status error or is missing the access token
            if (data?.status === "error" || !data?.access_token) {
                const detail = data?.detail || data?.message || "Login failed";
                throw new Error(detail);
            }

            dispatch(setCredentials({
                token: data.access_token,
                user: data.user || { email }
            }));

            toast.success(data?.message || data?.detail || "Login successful!");
            navigate("/dashboard");
        } catch (error) {
            console.error("Login error details:", error);
            const errorMsg = getErrorMessage(error);
            toast.error(errorMsg);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex h-screen w-full overflow-hidden bg-[#F8FAFC] dark:bg-gray-900 transition-colors relative">
            {/* Theme Toggle in Top Right Corner */}
            <div className="absolute top-6 right-6 z-50">
                <ThemeToggle />
            </div>

            {/* Left Column - Image */}
            <div className="hidden lg:flex w-1/2 p-4">
                <div
                    className="w-full h-full rounded-2xl shadow-xl overflow-hidden bg-cover bg-center"
                    style={{ backgroundImage: `url(${loginBg})` }}
                />
            </div>

            {/* Right Column - Form */}
            <div className="flex-1 flex flex-col justify-center items-center p-8 bg-[#F8FAFC] dark:bg-gray-900 transition-colors">
                <div className="w-full max-w-[400px]">

                    {/* Header Branding */}
                    <div className="text-center mb-8">
                        <h1 className="text-4xl font-bold text-[#3B82F6] tracking-tight mb-1">GIS</h1>
                        <p className="text-sm font-medium text-[#60A5FA]">Geographic Information Platform</p>
                    </div>

                    {/* Titles */}
                    <div className="text-center mb-8">
                        <h2 className="text-2xl font-bold text-gray-800 dark:text-white mb-1">Login To Your Account</h2>
                        <p className="text-sm text-gray-400 dark:text-gray-500">Please select the appropriate Login</p>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleLogin} className="space-y-5">

                        {/* Email Field */}
                        <div>
                            <label className="block text-sm font-bold text-gray-800 dark:text-gray-200 mb-1.5">
                                Email ID
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400 dark:text-gray-500">
                                    <Mail size={18} strokeWidth={2} />
                                </div>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="login_id@email.com"
                                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors shadow-sm text-sm"
                                    required
                                />
                            </div>
                        </div>

                        {/* Password Field */}
                        <div>
                            <label className="block text-sm font-bold text-gray-800 dark:text-gray-200 mb-1.5">
                                Password
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400 dark:text-gray-500">
                                    <Lock size={18} strokeWidth={2} />
                                </div>
                                <input
                                    type={showPassword ? "text" : "password"}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="*****************"
                                    className="w-full pl-10 pr-10 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors shadow-sm text-sm tracking-widest"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                                >
                                    {showPassword ? <EyeOff size={18} strokeWidth={2} /> : <Eye size={18} strokeWidth={2} />}
                                </button>
                            </div>
                        </div>

                        {/* Forgot Password */}
                        <div className="flex justify-end">
                            <Link to="/forgot-password" className="text-sm font-bold text-red-500 hover:text-red-600 transition-colors">
                                Forgot Password
                            </Link>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className={`w-full flex items-center justify-center gap-2 bg-[#3B82F6] hover:bg-blue-600 text-white font-bold py-3.5 px-4 rounded-xl shadow-lg shadow-blue-500/30 transition-all active:scale-[0.98] mt-2 ${isLoading ? "opacity-75 cursor-not-allowed" : ""}`}
                        >
                            {isLoading ? "Logging In..." : "Login"}
                            {!isLoading && <ArrowRight size={18} strokeWidth={2.5} />}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}