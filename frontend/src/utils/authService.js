import axios from "axios";
import { API_URLS } from "@/config/apiConfig.js";

// Note: Using layers backend or geo backend for auth? Assuming layers backend for now.
const authClient = axios.create({
    baseURL: API_URLS.LAYERS,
    headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    },
});

authClient.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export const authService = {
    login: async (email, password) => {
        // Modify the endpoint as needed depending on your backend
        const response = await authClient.post("/login", { email, password });
        return response.data;
    }
};
