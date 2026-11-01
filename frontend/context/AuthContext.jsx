"use client";
import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("intellitwin_token") : null;
    const savedUser = typeof window !== "undefined" ? localStorage.getItem("intellitwin_user") : null;
    if (saved) setToken(saved);
    if (savedUser) setUser(JSON.parse(savedUser));
    setHydrated(true);
  }, []);

  const persist = (t, u) => {
    setToken(t);
    setUser(u);
    localStorage.setItem("intellitwin_token", t);
    localStorage.setItem("intellitwin_user", JSON.stringify(u));
  };

  const login = useCallback(async (email, password) => {
    const data = await api.post("/auth/login", { email, password });
    persist(data.token, data.user);
    return data;
  }, []);

  const register = useCallback(async (name, email, password) => {
    const data = await api.post("/auth/register", { name, email, password });
    persist(data.token, data.user);
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("intellitwin_token");
    localStorage.removeItem("intellitwin_user");
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, setUser, hydrated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
