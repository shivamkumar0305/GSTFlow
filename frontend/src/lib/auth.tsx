"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearTokens, getAccessToken, setTokens } from "./api";
import type { Business } from "./types";

type AuthContextValue = {
  business: Business | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    business_name: string;
    gstin: string;
    pan: string;
  }) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [business, setBusiness] = useState<Business | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadMe = useCallback(async () => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }
    try {
      const me = await apiFetch<Business>("/api/auth/me/");
      setBusiness(me);
    } catch {
      clearTokens();
      setBusiness(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void loadMe());
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await apiFetch<{ access: string; refresh: string }>("/api/auth/login/", {
        method: "POST",
        body: { email, password },
        auth: false,
      });
      setTokens(data.access, data.refresh);
      await loadMe();
      router.push("/");
    },
    [loadMe, router]
  );

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      business_name: string;
      gstin: string;
      pan: string;
    }) => {
      const data = await apiFetch<{ access: string; refresh: string; business: Business }>(
        "/api/auth/register/",
        { method: "POST", body: payload, auth: false }
      );
      setTokens(data.access, data.refresh);
      setBusiness(data.business);
      router.push("/");
    },
    [router]
  );

  const logout = useCallback(() => {
    clearTokens();
    setBusiness(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ business, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
