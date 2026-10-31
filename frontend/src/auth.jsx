/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getRefresh, getStoredUser, getToken, setStoredUser, setToken, setRefresh } from "./api.js";
import EN from "./i18n/en.json";
import ROMAN from "./i18n/roman.json";

export function homeFor(user) {
  switch (user?.role) {
    case "mechanic": return "/mechanic";
    case "admin":
    case "reviewer": return "/admin/analytics";   // or "/review"
    default: return "/";
  }
}

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

function pickText(obj, base, lang) {
  if (!obj) return "";
  if (lang === "roman_ur" && obj[`${base}_roman`]) return obj[`${base}_roman`];
  return obj[`${base}_en`] || "";
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser);
  const loading = false;
  const [lang, setLangState] = useState(localStorage.getItem("lang") || "en");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") ||
    (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      setStoredUser(null);
    };
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, []);

  const login = useCallback(async (username, password) => {
    const result = await api("/accounts/auth/token/", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
    if (!result?.access || !result?.user) {
      throw new Error("The login response did not include an access token and user profile.");
    }
    setToken(result.access);
    setRefresh(result.refresh);
    setStoredUser(result.user);
    setUser(result.user);
    if (result.user.language) setLangState(result.user.language);
    return result.user;
  }, []);

  const register = useCallback(
    async (fields) => {
      await api("/accounts/auth/register/", { method: "POST", body: fields, auth: false });
      user = await login(fields.username, fields.password);
    },
    [login]
  );

  const registerMechanic = useCallback(async (fields) => {
    await api("/mechanic/register/", { method: "POST", body: fields, auth: false });
    user = await login(fields.username, fields.password);
  }, [login]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => current === "dark" ? "light" : "dark");
  }, []);

  const logout = useCallback(async () => {
    const refresh = getRefresh();
    if (refresh && getToken()) {
      try {
        await api("/accounts/auth/logout/", { method: "POST", body: { refresh } });
      } catch {
        // Always clear the local session even when the network is unavailable.
      }
    }
    setToken(null);
    setRefresh(null);
    setStoredUser(null);
    setUser(null);
  }, []);

  const setLang = useCallback(
    async (code) => {
      setLangState(code);
      localStorage.setItem("lang", code);
      if (getToken()) {
        try {
          await api("/accounts/me/", { method: "PATCH", body: { language: code } });
        } catch {
          /* the choice still applies on this device */
        }
      }
    },
    []
  );

  const value = useMemo(
    () => ({
      user,
      loading,
      lang,
      theme,
      toggleTheme,
      login,
      register,
      registerMechanic,
      logout,
      setLang,
      t: (key, options) => {
        const message = (lang === "roman_ur" ? ROMAN[key] : EN[key]) ?? EN[key] ?? key;
        return options ? Object.entries(options).reduce((result, [name, value]) => result.replaceAll(`{{${name}}}`, value), message) : message;
      },
      pick: (obj, base) => pickText(obj, base, lang),
    }),
    [user, loading, lang, theme, toggleTheme, login, register, registerMechanic, logout, setLang]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
