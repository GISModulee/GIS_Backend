import { useState } from "react";
import { Mail, ArrowRight } from "lucide-react";
import { useNavigate, Link } from "react-router-dom";
import toast from "react-hot-toast";
import loginBg from "@/assets/loginbg.jpeg";

export default function ForgotPassword() {
    const [email, setEmail] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const navigate = useNavigate();

    const handleReset = (e) => {
        e.preventDefault();
        setIsSubmitting(true);

        // Simulate API call for password reset
        setTimeout(() => {
            setIsSubmitting(false);
            toast.success("Password reset link sent! Check your email.");
            navigate("/login");
        }, 1500);
    };

    return (
        <div className="flex h-screen w-full overflow-hidden bg-[#F8FAFC]">
            {/* Left Column - Image */}
            <div className="hidden lg:flex w-1/2 p-4">
                <div
                    className="w-full h-full rounded-2xl shadow-xl overflow-hidden bg-cover bg-center"
                    style={{ backgroundImage: `url(${loginBg})` }}
                />
            </div>

            {/* Right Column - Form */}
            <div className="flex-1 flex flex-col justify-center items-center p-8">
                <div className="w-full max-w-[400px]">

                    {/* Header Branding */}
                    <div className="text-center mb-8">
                        <h1 className="text-4xl font-bold text-[#3B82F6] tracking-tight mb-1">GIS</h1>
                        <p className="text-sm font-medium text-[#60A5FA]">Geographic Information Platform</p>
                    </div>

                    {/* Titles */}
                    <div className="text-center mb-8">
                        <h2 className="text-2xl font-bold text-gray-800 mb-1">Forgot Password?</h2>
                        <p className="text-sm text-gray-400">Enter your email to receive a reset link</p>
                    </div>

                    {/* Form */}
                    <form onSubmit={handleReset} className="space-y-5">
                        {/* Email Field */}
                        <div>
                            <label className="block text-sm font-bold text-gray-800 mb-1.5">
                                Email ID
                            </label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
                                    <Mail size={18} strokeWidth={2} />
                                </div>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="login_id@email.com"
                                    className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors shadow-sm"
                                    required
                                />
                            </div>
                        </div>

                        {/* Back to Login */}
                        <div className="flex justify-end">
                            <Link to="/login" className="text-sm font-bold text-gray-500 hover:text-gray-700 transition-colors">
                                Back to Login
                            </Link>
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className={`w-full flex items-center justify-center gap-2 bg-[#3B82F6] hover:bg-blue-600 text-white font-bold py-3.5 px-4 rounded-xl shadow-lg shadow-blue-500/30 transition-all active:scale-[0.98] mt-2 ${isSubmitting ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                            {isSubmitting ? "Sending..." : "Reset Password"}
                            {!isSubmitting && <ArrowRight size={18} strokeWidth={2.5} />}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}