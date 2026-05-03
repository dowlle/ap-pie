import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getAuthMe, type AuthUser } from "../api";

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  authEnabled: boolean;
  loading: boolean;
  justApproved: boolean;
  dismissJustApproved: () => void;
  login: (next?: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  authEnabled: true,
  loading: true,
  justApproved: false,
  dismissJustApproved: () => {},
  login: () => {},
  logout: async () => {},
});

const APPROVAL_POLL_INTERVAL_MS = 30_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [justApproved, setJustApproved] = useState(false);
  const wasApprovedRef = useRef<boolean>(false);

  useEffect(() => {
    getAuthMe()
      .then((u) => {
        setUser(u);
        wasApprovedRef.current = !!(u?.is_approved || u?.is_admin);
      })
      .catch((err) => {
        setUser(null);
        // If the auth endpoint returns 401, auth may just not be configured.
        // Probe an otherwise-protected route: if it succeeds, auth is off.
        if (err.message?.includes("401")) {
          fetch("/api/games?limit=1").then((r) => {
            if (r.ok) setAuthEnabled(false);
          }).catch(() => {});
        }
      })
      .finally(() => setLoading(false));
  }, []);

  // Poll /api/auth/me while the user is logged in but waiting for approval,
  // so the UI flips as soon as an admin approves them without a manual refresh.
  useEffect(() => {
    if (!authEnabled) return;
    if (!user) return;
    if (user.is_approved || user.is_admin) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const fresh = await getAuthMe();
        if (cancelled) return;
        setUser(fresh);
        const approvedNow = !!(fresh.is_approved || fresh.is_admin);
        if (approvedNow && !wasApprovedRef.current) {
          setJustApproved(true);
        }
        wasApprovedRef.current = approvedNow;
      } catch {
        // swallow - user may have logged out in another tab; next poll will fail too
      }
    };
    const interval = setInterval(tick, APPROVAL_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [authEnabled, user]);

  const login = (next?: string) => {
    const url = next
      ? `/api/auth/login?next=${encodeURIComponent(next)}`
      : "/api/auth/login";
    window.location.href = url;
  };

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setUser(null);
    wasApprovedRef.current = false;
    setJustApproved(false);
  };

  const dismissJustApproved = () => setJustApproved(false);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        authEnabled,
        loading,
        justApproved,
        dismissJustApproved,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
