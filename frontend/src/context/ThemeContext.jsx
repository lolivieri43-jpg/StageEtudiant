import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "../lib/api";

const ThemeContext = createContext(null);
const VALID = ["light", "dark", "system"];

function resolveEffective(pref) {
  if (pref === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return pref === "dark" ? "dark" : "light";
}

function applyToDom(effective) {
  const root = document.documentElement;
  if (effective === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
  root.setAttribute("data-theme", effective);
}

export const ThemeProvider = ({ children, user }) => {
  // Initial value from localStorage (or system default)
  const [preference, setPreference] = useState(() => {
    const saved = localStorage.getItem("theme_preference");
    return VALID.includes(saved) ? saved : "system";
  });

  // When the connected user's preference arrives, hydrate it
  useEffect(() => {
    if (user?.theme_preference && VALID.includes(user.theme_preference)) {
      setPreference(user.theme_preference);
      localStorage.setItem("theme_preference", user.theme_preference);
    }
  }, [user?.theme_preference]);

  // Apply theme to <html> whenever preference changes
  useEffect(() => {
    applyToDom(resolveEffective(preference));
  }, [preference]);

  // Listen to system color-scheme changes when in "system" mode
  useEffect(() => {
    if (preference !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyToDom(resolveEffective("system"));
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [preference]);

  const setTheme = useCallback(async (pref) => {
    if (!VALID.includes(pref)) return;
    setPreference(pref);
    localStorage.setItem("theme_preference", pref);
    if (user?.user_id) {
      try { await api.patch("/me/theme", { theme_preference: pref }); } catch { /* offline OK */ }
    }
  }, [user?.user_id]);

  const toggle = useCallback(() => {
    const next = resolveEffective(preference) === "dark" ? "light" : "dark";
    setTheme(next);
  }, [preference, setTheme]);

  const effective = resolveEffective(preference);
  return (
    <ThemeContext.Provider value={{ preference, effective, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
