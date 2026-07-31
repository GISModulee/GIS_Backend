// src/api/client.js
import axios from "axios";
import { API_URLS, API_CONFIG } from "@/config/apiConfig.js";

const commonHeaders = {
  "Content-Type": "application/json",
};

// ── Geo/boundary backend (self-hosted) ────────────────────
export const geoClient = axios.create({
  baseURL: API_URLS.GEO,
  timeout: API_CONFIG.TIMEOUT,
  headers: commonHeaders,
});

// ── Layers/features backend (ngrok) ──────────────────────
export const layersClient = axios.create({
  baseURL: API_URLS.LAYERS,
  timeout: API_CONFIG.TIMEOUT,
  // headers: {
  //   ...commonHeaders,
  //   "ngrok-skip-browser-warning": "true",
  // },
});

// ── Interceptors (both clients) ───────────────────────────
[geoClient, layersClient].forEach((client) => {
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (import.meta.env.DEV) {
      console.log(`[API →] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    }
    return config;
  });

  client.interceptors.response.use(
    (res) => {
      // Check if backend returned a 200 OK but with an authentication error payload
      if (res.data && res.data.status === "error" &&
        (res.data.detail?.includes("authenticated") || res.data.detail?.includes("token"))) {
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
      // If the backend is off (network/connection error), redirect to login and flag for toast msg
      if (!err.response) {
        if (window.location.pathname !== "/login") {
          const theme = localStorage.getItem("theme");
          localStorage.clear();
          if (theme) localStorage.setItem("theme", theme);
          sessionStorage.setItem("network_error_toast", "true");
          window.location.href = "/login";
        }
        return Promise.reject(err);
      }

      // If we get a 401 Unauthorized, clear state and redirect to login
      if (err.response?.status === 401) {
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
});