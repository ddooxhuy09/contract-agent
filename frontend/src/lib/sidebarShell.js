import { useState } from "react";

const STORAGE_KEY = "cl-sidebar-collapsed";

export function useSidebarCollapsed(defaultCollapsed = false) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw === null) return defaultCollapsed;
      return raw === "1";
    } catch {
      return defaultCollapsed;
    }
  });

  const setAndPersist = (value) => {
    const next = typeof value === "function" ? value(collapsed) : value;
    setCollapsed(next);
    try {
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      /* ignore */
    }
  };

  return [collapsed, setAndPersist];
}

/** Main content offset for shell (desktop sidebar + mobile top bar) */
export function shellMainClass(collapsed) {
  return `flex-1 min-h-screen pt-11 md:pt-0 pb-3 md:pb-0 ${
    collapsed ? "md:ml-14" : "md:ml-52"
  }`;
}
