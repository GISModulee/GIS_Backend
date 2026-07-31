import axios from "axios";
import { API_URLS, API_CONFIG } from "@/config/apiConfig.js";

const axiosInstance = axios.create({
  timeout: API_CONFIG.TIMEOUT,
  headers: {
    ...API_CONFIG.HEADERS,
  },
});

axiosInstance.interceptors.request.use((config) => {
  // Route to the appropriate backend base URL based on path
  if (config.url && config.url.startsWith("/boundaries")) {
    config.baseURL = API_URLS.GEO;
  } else {
    config.baseURL = API_URLS.LAYERS;
  }

  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  if (import.meta.env.DEV) {
    console.log(`[API →] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
  }
  return config;
});

axiosInstance.interceptors.response.use(
  (res) => {
    const isBoundaryRequest = res.config?.url && res.config.url.startsWith("/boundaries");

    // Check if backend returned a 200 OK but with an authentication error payload
    if (
      !isBoundaryRequest &&
      res.data &&
      res.data.status === "error" &&
      (res.data.detail?.includes("authenticated") || res.data.detail?.includes("token"))
    ) {
      const theme = localStorage.getItem("theme");
      localStorage.clear();
      if (theme) localStorage.setItem("theme", theme);
      window.location.href = "/login";
      return Promise.reject(new Error(res.data.detail));
    }

    if (res.data && res.data.status === "error") {
      const error = new Error(res.data.detail || res.data.message || "API Error");
      error.response = res;
      return Promise.reject(error);
    }

    return res;
  },
  async (err) => {
    const isBoundaryRequest = err.config?.url && err.config.url.startsWith("/boundaries");

    // If the backend is off (network/connection error), redirect to login and flag for toast msg
    if (!err.response) {
      if (!isBoundaryRequest && window.location.pathname !== "/login") {
        const theme = localStorage.getItem("theme");
        localStorage.clear();
        if (theme) localStorage.setItem("theme", theme);
        sessionStorage.setItem("network_error_toast", "true");
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }

    // If we get a 401 Unauthorized, clear state and redirect to login
    if (err.response?.status === 401 && !isBoundaryRequest) {
      const theme = localStorage.getItem("theme");
      localStorage.clear();
      if (theme) localStorage.setItem("theme", theme);
      window.location.href = "/login";
      return Promise.reject(err);
    }

    if (import.meta.env.DEV) {
      console.error(`[API ✕]`, err?.response?.status, err?.config?.url, err?.response?.data);
    }
    return Promise.reject(err);
  }
);

export default axiosInstance;
