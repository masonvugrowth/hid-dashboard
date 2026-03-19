import { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const AuthContext = createContext(null);

const TOKEN_KEY = "hid_token";
const USER_KEY  = "hid_user";

// Attach JWT to every request
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Dev mode: skip auth when running locally without backend
const DEV_USER = import.meta.env.DEV ? {
  id: "dev-admin",
  email: "admin@hid.local",
  name: "Dev Admin",
  role: "admin",
} : null;

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(() => {
    if (DEV_USER) return DEV_USER;
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  });
  const [loading, setLoading] = useState(!DEV_USER);

  // Validate stored token on mount (skip in dev mode)
  useEffect(() => {
    if (DEV_USER) { setLoading(false); return; }
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) { setLoading(false); return; }
    axios.get("/api/auth/me")
      .then(r => setUser(r.data.data))
      .catch(() => { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const r = await axios.post("/api/auth/login", { email, password });
    const { token, user: u } = r.data.data;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY,  JSON.stringify(u));
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
