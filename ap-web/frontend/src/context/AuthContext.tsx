import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getAuthMe, type AuthUser } from "../api";

/**
 * Role vocabulary on the frontend (per 2026-05-04 conversation):
 *   - Admin  : the owner (is_owner=true). Full control, sees all admin tools.
 *   - Host   : approved logged-in user (is_approved=true, !is_admin). Can
 *              create / manage their own rooms, browse the APWorlds index.
 *   - User   : logged in but not approved. Lands on the Landing page with
 *              the "ping Appie on Discord" CTA. Can still submit YAMLs to
 *              any room they have a URL for.
 *   - Public : no session. Only reachable via /r/<id> or /play/<seed>.
 *
 * The owner-only "view as" toggle (DEVEX-02) lets Stef preview the Admin /
 * Host / User chrome without re-logging-in or making a second account. It
 * is FRONTEND-ONLY: the backend always trusts the real session, so any
 * server-gated behaviour (FEAT-13 submitter username exposure, market
 * mutation gates, /api/admin middleware) is unaffected by the toggle.
 * Public preview is served by opening /r/<id> in an incognito tab - the
 * toggle deliberately does not include a Public option.
 */
export type ViewAsRole = "admin" | "host" | "user";
const VIEW_AS_STORAGE_KEY = "ap-pie:view-as";

interface AuthContextType {
  /** Effective user with the view-as override applied. Read this in every
   *  consumer that gates UI on role. is_admin / is_approved here reflect
   *  the *intended view*, not the raw session. */
  user: AuthUser | null;
  /** Raw user from /api/auth/me, no override applied. Read this only for
   *  the toggle UI itself or for "what is my real role?" introspection. */
  rawUser: AuthUser | null;
  isAuthenticated: boolean;
  authEnabled: boolean;
  loading: boolean;
  justApproved: boolean;
  dismissJustApproved: () => void;
  /** True when the raw session belongs to the owner (Stef). Gates the
   *  view-as toggle's visibility in the NavBar. */
  isOwner: boolean;
  /** Current view-as selection. Always "admin" for non-owners (override
   *  is a no-op). */
  viewAs: ViewAsRole;
  /** Setter for the view-as selection. No-op for non-owners. */
  setViewAs: (role: ViewAsRole) => void;
  login: (next?: string) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  rawUser: null,
  isAuthenticated: false,
  authEnabled: true,
  loading: true,
  justApproved: false,
  dismissJustApproved: () => {},
  isOwner: false,
  viewAs: "admin",
  setViewAs: () => {},
  login: () => {},
  logout: async () => {},
});

const APPROVAL_POLL_INTERVAL_MS = 30_000;

function readPersistedViewAs(): ViewAsRole {
  try {
    const v = localStorage.getItem(VIEW_AS_STORAGE_KEY);
    if (v === "host" || v === "user" || v === "admin") return v;
  } catch {
    // localStorage may be unavailable (private mode, etc.)
  }
  return "admin";
}

function applyViewAs(raw: AuthUser | null, viewAs: ViewAsRole, isOwner: boolean): AuthUser | null {
  if (!raw) return null;
  // Override only applies for the owner; everyone else sees their real role
  // unconditionally so a leaked persisted toggle can never demote a real admin.
  if (!isOwner) return raw;
  switch (viewAs) {
    case "admin":
      return raw;
    case "host":
      return { ...raw, is_admin: false, is_approved: true };
    case "user":
      return { ...raw, is_admin: false, is_approved: false };
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [rawUser, setRawUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [justApproved, setJustApproved] = useState(false);
  const [viewAs, setViewAsState] = useState<ViewAsRole>(readPersistedViewAs);
  const wasApprovedRef = useRef<boolean>(false);

  useEffect(() => {
    getAuthMe()
      .then((u) => {
        setRawUser(u);
        wasApprovedRef.current = !!(u?.is_approved || u?.is_admin);
      })
      .catch((err) => {
        setRawUser(null);
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
    if (!rawUser) return;
    if (rawUser.is_approved || rawUser.is_admin) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const fresh = await getAuthMe();
        if (cancelled) return;
        setRawUser(fresh);
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
  }, [authEnabled, rawUser]);

  const isOwner = !!rawUser?.is_owner;

  const setViewAs = (role: ViewAsRole) => {
    setViewAsState(role);
    try {
      localStorage.setItem(VIEW_AS_STORAGE_KEY, role);
    } catch {
      // ignore - same fallback as readPersistedViewAs
    }
  };

  const user = useMemo(
    () => applyViewAs(rawUser, viewAs, isOwner),
    [rawUser, viewAs, isOwner],
  );

  const login = (next?: string) => {
    const url = next
      ? `/api/auth/login?next=${encodeURIComponent(next)}`
      : "/api/auth/login";
    window.location.href = url;
  };

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setRawUser(null);
    wasApprovedRef.current = false;
    setJustApproved(false);
    // Reset view-as on logout so a fresh login lands on the default chrome.
    setViewAs("admin");
  };

  const dismissJustApproved = () => setJustApproved(false);

  return (
    <AuthContext.Provider
      value={{
        user,
        rawUser,
        isAuthenticated: !!rawUser,
        authEnabled,
        loading,
        justApproved,
        dismissJustApproved,
        isOwner,
        viewAs,
        setViewAs,
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
