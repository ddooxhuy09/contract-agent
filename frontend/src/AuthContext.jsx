import { useEffect, useState } from "react";
import { AuthContext } from "./authContextObject";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const STORAGE_KEY = "contractlens_auth";

function loadStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => loadStored());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const persist = (next) => {
    setAuth(next);
    if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else localStorage.removeItem(STORAGE_KEY);
  };

  const signIn = async (email, password) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { error: { message: data.detail || res.statusText } };
    }
    const data = await res.json();
    persist({
      access_token: data.access_token,
      user: { id: data.user_id, email: data.email },
    });
    return { error: null };
  };

  const signUp = async (email, password) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return { error: { message: data.detail || res.statusText } };
    }
    const data = await res.json();
    persist({
      access_token: data.access_token,
      user: { id: data.user_id, email: data.email },
    });
    return { error: null };
  };

  const signOut = async () => {
    persist(null);
  };

  const value = {
    session: auth
      ? { access_token: auth.access_token, user: auth.user }
      : null,
    user: auth?.user || null,
    accessToken: auth?.access_token || null,
    loading,
    signIn,
    signUp,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
