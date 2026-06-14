import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../lib/api";

const AuthContext = createContext(null);

/**
 * Auth lifecycle:
 *  - JWT lives in an HttpOnly `access_token` cookie set by /auth/login,
 *    /auth/register and /auth/google/callback (XSS-safe).
 *  - For backwards compatibility we still read any legacy token from
 *    localStorage and send it as Authorization Bearer; new sessions never
 *    write to localStorage.
 *  - On mount we always call /auth/me — the browser will send the cookie
 *    automatically (axios is configured with withCredentials=true).
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Legacy custom-Google-OAuth flow returns the JWT in URL fragment "#token=…"
    // We still honor it (writes to localStorage) until that path is fully retired.
    if (typeof window !== "undefined" && window.location.hash?.includes("token=")) {
      const params = new URLSearchParams(window.location.hash.slice(1));
      const t = params.get("token");
      if (t) {
        localStorage.setItem("token", t);
        window.history.replaceState({}, "", window.location.pathname + window.location.search);
      }
    }
    // Emergent Google session pathway — handled by /auth/session flow.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    // Cookie is the source of truth; legacy localStorage write removed.
    // (We still keep what's there if the browser hasn't migrated yet — login
    // overwrites by setting the new HttpOnly cookie via Set-Cookie.)
    localStorage.removeItem("token");
    setUser(data.user);
    return data.user;
  };

  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.removeItem("token");
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      console.warn("logout API failed (continuing local logout):", err?.message || err);
    }
    localStorage.removeItem("token");
    setUser(null);
    window.location.href = "/";
  };

  const refreshUser = async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (err) {
      console.warn("refreshUser failed:", err?.message || err);
    }
  };

  return (
    <AuthContext.Provider value={{ user, setUser, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
