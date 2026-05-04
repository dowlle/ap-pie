import { BrowserRouter, Routes, Route, NavLink, Navigate, Link } from "react-router-dom";
import GameList from "./pages/GameList";
import GameDetail from "./pages/GameDetail";
import Summary from "./pages/Summary";
import Servers from "./pages/Servers";
import APWorlds from "./pages/APWorlds";
import Market from "./pages/Market";
import MarketLanding from "./pages/MarketLanding";
import MarketTracker from "./pages/MarketTracker";
import Rooms from "./pages/Rooms";
import RoomDetail from "./pages/RoomDetail";
import RoomPublic from "./pages/RoomPublic";
import TrackerPage from "./pages/Tracker";
import Admin from "./pages/Admin";
import Play from "./pages/Play";
import Landing from "./pages/Landing";
import PublicLayout from "./components/PublicLayout";
import { refreshData } from "./api";
import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { FeaturesProvider, useFeature } from "./context/FeaturesContext";
import AuthButton from "./components/AuthButton";

function NavBar() {
  const { user, authEnabled, loading, isOwner, viewAs, setViewAs } = useAuth();
  const generationOn = useFeature("generation");
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshData();
      window.location.reload();
    } finally {
      setRefreshing(false);
    }
  };

  // MVP scope: Archipelago Pie ships as a YAML collector. Hosts (approved
  // users) see Rooms; everything else (Market, Tracker, Games, Servers,
  // Summary, Refresh) is admin-only chrome. When auth is disabled (dev) or
  // still resolving, treat it as full-access so the nav doesn't flash empty
  // during boot. When the generation feature flag is OFF, the AP-server-
  // related links are hidden even from admins - there's nothing on those
  // pages without server-side gen.
  //
  // `user` here is the *effective* user from AuthContext - already accounts
  // for the owner-only view-as override, so flipping the toggle to "host" or
  // "user" hides the admin nav exactly as it would for a real host or user.
  const isAdmin = !!user?.is_admin;
  const isApproved = !!(user?.is_approved || user?.is_admin);
  const authBypassed = !authEnabled || loading;
  const showRoomsLink = authBypassed || isApproved;
  const showAdminTools = authBypassed || isAdmin;

  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">Archipelago Pie</Link>
      <div className="nav-links">
        {showRoomsLink && <NavLink to="/rooms">Rooms</NavLink>}
        {/* APWorlds is now visible to any approved host (FEAT-21). Even with
            generation OFF in production, the index browser is useful: hosts
            pin per-room versions, players follow links to install locally. */}
        {showRoomsLink && <NavLink to="/apworlds">APWorlds</NavLink>}
        {showAdminTools && (
          <>
            <NavLink to="/market">Market</NavLink>
            {generationOn && <NavLink to="/tracker">Tracker</NavLink>}
            {generationOn && <NavLink to="/" end>Games</NavLink>}
            {generationOn && <NavLink to="/servers">Servers</NavLink>}
            {generationOn && <NavLink to="/summary">Summary</NavLink>}
            {generationOn && (
              <button onClick={handleRefresh} disabled={refreshing} className="btn btn-sm">
                {refreshing ? "Refreshing..." : "Refresh"}
              </button>
            )}
          </>
        )}
        {user?.is_admin && <NavLink to="/admin">Admin</NavLink>}
        {/* Owner-only role-preview toggle (DEVEX-02). Renders nothing for
            non-owners. Frontend-only override; backend always trusts the
            real session, so server-gated behaviour (FEAT-13 sanitisation,
            /api/admin middleware) is unaffected. Public preview is served
            by opening /r/<id> in an incognito tab. */}
        {isOwner && <ViewAsToggle viewAs={viewAs} setViewAs={setViewAs} />}
        <AuthButton />
      </div>
    </nav>
  );
}

function ViewAsToggle({
  viewAs,
  setViewAs,
}: {
  viewAs: "admin" | "host" | "user";
  setViewAs: (role: "admin" | "host" | "user") => void;
}) {
  return (
    <label
      className="view-as-toggle"
      title="Preview the UI as a different role. Frontend-only - backend permissions are unaffected. Open /r/<id> in an incognito tab to preview the public (logged-out) experience."
    >
      <span className="view-as-label">View as</span>
      <select
        value={viewAs}
        onChange={(e) => setViewAs(e.target.value as "admin" | "host" | "user")}
      >
        <option value="admin">Admin</option>
        <option value="host">Host</option>
        <option value="user">User</option>
      </select>
    </label>
  );
}

/**
 * The `/` landing decides per audience:
 *   - dev mode (auth disabled) or admin: legacy GameList (admin tooling)
 *   - approved non-admin host: redirect to /rooms (their working surface)
 *   - anonymous or pending-approval visitor: Landing (marketing + Discord CTA
 *     + closed-beta queue notice). Landing handles both states internally,
 *     and the auth poll in AuthContext flips them onto /rooms automatically
 *     once an admin approves them.
 */
function HomeView() {
  const { user, authEnabled, loading } = useAuth();
  if (loading) return null;
  if (!authEnabled) return <GameList />;
  if (user?.is_admin) return <GameList />;
  if (user?.is_approved) return <Navigate to="/rooms" replace />;
  return <Landing />;
}

function RequireApproval({ children }: { children: React.ReactNode }) {
  const { user, authEnabled, loading } = useAuth();
  if (loading) return null;
  if (!authEnabled) return <>{children}</>;
  if (!user) return <Navigate to="/" replace />;
  if (!user.is_approved && !user.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

/**
 * Renders the admin nav + container + approval toast for non-public routes.
 * Public routes (/r and /play) opt out via the PublicLayout wrapper, which
 * gives them a stripped-down shell appropriate for invited players.
 */
function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NavBar />
      <ApprovalToast />
      <main className="container">{children}</main>
    </>
  );
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes - minimal shell, no admin nav. */}
      <Route element={<PublicLayout />}>
        <Route path="/play/:seed" element={<Play />} />
        <Route path="/r/:id" element={<RoomPublic />} />
      </Route>

      {/* Admin / authenticated routes - full chrome. */}
      <Route path="/market" element={<AdminShell><MarketLanding /></AdminShell>} />
      <Route path="/market/:trackerId" element={<AdminShell><MarketTracker /></AdminShell>} />
      <Route path="/admin" element={<AdminShell><RequireAdmin><Admin /></RequireAdmin></AdminShell>} />
      <Route path="/" element={<AdminShell><HomeView /></AdminShell>} />
      <Route path="/rooms" element={<AdminShell><RequireApproval><Rooms /></RequireApproval></AdminShell>} />
      <Route path="/rooms/:id" element={<AdminShell><RequireApproval><RoomDetail /></RequireApproval></AdminShell>} />
      <Route path="/tracker" element={<AdminShell><RequireApproval><TrackerPage /></RequireApproval></AdminShell>} />
      <Route path="/games/:seed" element={<AdminShell><RequireApproval><GameDetail /></RequireApproval></AdminShell>} />
      <Route path="/games/:seed/market" element={<AdminShell><RequireApproval><Market /></RequireApproval></AdminShell>} />
      <Route path="/servers" element={<AdminShell><RequireApproval><Servers /></RequireApproval></AdminShell>} />
      <Route path="/apworlds" element={<AdminShell><RequireApproval><APWorlds /></RequireApproval></AdminShell>} />
      <Route path="/summary" element={<AdminShell><RequireApproval><Summary /></RequireApproval></AdminShell>} />
    </Routes>
  );
}

function ApprovalToast() {
  const { justApproved, dismissJustApproved } = useAuth();
  if (!justApproved) return null;
  return (
    <div className="approval-toast" role="status">
      <span>You're now a host. You can create your own rooms and manage YAMLs.</span>
      <button type="button" className="btn btn-sm" onClick={dismissJustApproved}>Dismiss</button>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <FeaturesProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </FeaturesProvider>
    </AuthProvider>
  );
}

export default App;
