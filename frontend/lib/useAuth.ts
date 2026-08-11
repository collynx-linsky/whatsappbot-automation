"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { Role, User } from "@/types";
import { dashboardPathForRole, getAccessToken, getStoredUser } from "./auth";

interface RequireAuthOptions {
  /** If set, redirects users whose role doesn't match to their own dashboard
   *  instead of rendering this page for them. The backend independently
   *  enforces this on every real API call regardless — this only avoids a
   *  confusing broken-page UX for someone who navigates here directly. */
  requireRole?: Role;
}

/**
 * Client-side route guard: redirects to /login if no session is stored.
 * There's no server-side session to check (JWTs live in localStorage), so
 * this runs in an effect after mount rather than blocking render on the
 * server — the page briefly shows a loading state first.
 */
export function useRequireAuth(options: RequireAuthOptions = {}): {
  user: User | null;
  ready: boolean;
} {
  const router = useRouter();
  const { requireRole } = options;
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getAccessToken();
    const storedUser = getStoredUser();
    if (!token || !storedUser) {
      router.replace("/login");
      return;
    }
    if (requireRole && storedUser.role !== requireRole) {
      router.replace(dashboardPathForRole(storedUser.role));
      return;
    }
    // Reading localStorage must happen post-mount (it's unavailable during
    // SSR) — this is the one legitimate case for setState-in-effect here,
    // not a data fetch that belongs in render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUser(storedUser);
    setReady(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requireRole]);

  return { user, ready };
}
