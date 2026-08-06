import axios from "axios";
import { API_URLS, API_CONFIG } from "@/config/apiConfig.js";

const axiosInstance = axios.create({
  // timeout: API_CONFIG.TIMEOUT,
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

    // Do not redirect or clear storage if the request was explicitly canceled/aborted
    if (axios.isCancel?.(err) || err.name === "CanceledError" || err.code === "ERR_CANCELED") {
      return Promise.reject(err);
    }

    // If the backend has a connection error or timeout, do not force-log out the user.
    // Wiping local storage on a transient network overload is highly disruptive.
    if (!err.response) {
      if (import.meta.env.DEV) {
        console.error("[API Network Error]:", err);
      }
      return Promise.reject(err);
    }

    // If we get a 401 Unauthorized, clear state and redirect to login
    if (err.response?.status === 401 && !isBoundaryRequest) {
      if (window.location.pathname !== "/login") {
        const theme = localStorage.getItem("theme");
        localStorage.clear();
        if (theme) localStorage.setItem("theme", theme);
        window.location.href = "/login";
      }
      return Promise.reject(err);
    }

    // If we get a 404 or 503 error, append request_id to error details so components display it without duplicating toasts
    if (err.response?.status === 404 || err.response?.status === 503) {
      const errorData = err.response?.data;
      const detail = errorData?.detail || errorData?.message || "Server Error";
      const requestId = errorData?.request_id;
      const displayMsg = requestId ? `${detail} (Request ID: ${requestId})` : detail;

      if (errorData) {
        errorData.detail = displayMsg;
        errorData.message = displayMsg;
      }
      err.message = displayMsg;
    }

    if (import.meta.env.DEV) {
      console.error(`[API ✕]`, err?.response?.status, err?.config?.url, err?.response?.data);
    }
    return Promise.reject(err);
  }
);

export default axiosInstance;
