import axios from "axios";

const RAW = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");
// Tolerate both styles of REACT_APP_BACKEND_URL:
//   "https://example.com"        → we add "/api"
//   "https://example.com/api"    → already has "/api", keep as-is (prevents /api/api/...)
export const API = /\/api$/.test(RAW) ? RAW : `${RAW}/api`;
// Origin without the trailing /api — useful to build manual paths like `${ORIGIN}/api/files/xyz`
export const BACKEND_ORIGIN = RAW.replace(/\/api$/, "");

// Helper: build a backend URL given a path. Accepts either "/api/foo" or "foo".
// Guarantees no double "/api/api/" no matter how REACT_APP_BACKEND_URL was set.
export const backendUrl = (path = "") => {
  if (!path) return API;
  if (/^https?:\/\//i.test(path)) return path;
  const clean = path.startsWith("/") ? path : `/${path}`;
  if (clean.startsWith("/api/") || clean === "/api") {
    return `${BACKEND_ORIGIN}${clean}`;
  }
  return `${API}${clean}`;
};

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
