import { lazy, Suspense, useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate, Link, useLocation } from "react-router-dom";
// The two views behind "/" stay in the entry chunk: they are what a reload of
// ap-pie.com paints, so making them wait on a second request would only move
// the delay. Every other route is a lazy chunk, which keeps react-markdown,
// js-yaml/yaml and diff - the builder, guide and room dependencies - out of
// the bundle a first-time visitor must download and parse before the app can
// replace the server-rendered fallback.
import GameList from "./pages/GameList";
import Landing from "./pages/Landing";
const GameDetail = lazy(() => import("./pages/GameDetail"));
const Summary = lazy(() => import("./pages/Summary"));
const Servers = lazy(() => import("./pages/Servers"));
const APWorlds = lazy(() => import("./pages/APWorlds"));
const Market = lazy(() => import("./pages/Market"));
const MarketLanding = lazy(() => import("./pages/MarketLanding"));
const MarketTracker = lazy(() => import("./pages/MarketTracker"));
const Rooms = lazy(() => import("./pages/Rooms"));
const RoomDetail = lazy(() => import("./pages/RoomDetail"));
const RoomPublic = lazy(() => import("./pages/RoomPublic"));
const TrackerPage = lazy(() => import("./pages/Tracker"));
const Admin = lazy(() => import("./pages/Admin"));
const AdminApworldRequests = lazy(() => import("./pages/AdminApworldRequests"));
const Play = lazy(() => import("./pages/Play"));
const MyArea = lazy(() => import("./pages/MyArea"));
const YamlBuilderPage = lazy(() => import("./pages/YamlBuilderPage"));
const YamlBuilderLanding = lazy(() => import("./pages/YamlBuilderLanding"));
const NotFound = lazy(() => import("./pages/NotFound"));
const StyleGuide = lazy(() => import("./pages/StyleGuide"));
const APWorldDetailPreview = lazy(() => import("./pages/APWorldDetailPreview"));
const AccountRecovery = lazy(() => import("./pages/AccountRecovery"));
import PublicLayout from "./components/PublicLayout";
import { refreshData } from "./api";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { FeaturesProvider, useFeature } from "./context/FeaturesContext";
import { DeploymentProvider } from "./context/DeploymentContext";
import AuthButton from "./components/AuthButton";
import DeploymentBanner from "./components/DeploymentBanner";
import { trackPageView } from "./lib/analytics";
import PublicRouteHead from "./lib/PublicRouteHead";

function NavBar() {
  const { user, authEnabled, loading, isOwner, viewAs, setViewAs } = useAuth();
  const generationOn = useFeature("generation");
  const [refreshing, setRefreshing] = useState(false);
  // FEAT-27: hamburger drawer for narrow viewports. CSS hides the toggle
  // button above 768px and forces the drawer open, so this state is a no-op
  // on desktop.
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const closeMenu = () => setMenuOpen(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshData();
      window.location.reload();
    } finally {
      setRefreshing(false);
    }
  };

  // MVP scope: Archipelago Pie ships as a YAML collector. When open room
  // creation is enabled, every signed-in user sees Rooms; everything else
  // (Market, Tracker, Games, Servers,
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
  const openRoomCreation = useFeature("open_room_creation");
  const canUseRooms = !!user && (isApproved || openRoomCreation);
  const authBypassed = !authEnabled || loading;
  const showRoomsLink = authBypassed || canUseRooms;
  const showAdminTools = authBypassed || isAdmin;

  return (
    <nav className="navbar">
      <Link to={canUseRooms ? "/rooms" : "/"} className="nav-brand" onClick={closeMenu}>Archipelago Pie</Link>
      <button
        type="button"
        className="nav-hamburger"
        aria-expanded={menuOpen}
        aria-controls="nav-drawer"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        onClick={() => setMenuOpen(o => !o)}
      >
        <span className="nav-hamburger-bar" />
        <span className="nav-hamburger-bar" />
        <span className="nav-hamburger-bar" />
      </button>
      <div
        id="nav-drawer"
        className="nav-links"
        data-open={menuOpen ? "true" : undefined}
        onClick={(e) => {
          // Close the drawer when a NavLink (or any anchor / button) inside
          // it is clicked - keeps the route-change UX self-evident on
          // mobile without wiring a router listener.
          const target = e.target as HTMLElement;
          if (target.closest("a, button")) closeMenu();
        }}
      >
        {/* FEAT-39: Guides are server-rendered pages outside the SPA, so this
            is a plain anchor (full navigation), not a NavLink. Visible to
            everyone and rides the hamburger drawer on mobile. */}
        <a href="/guides">Guides</a>
        {showRoomsLink && <NavLink to="/rooms">Rooms</NavLink>}
        {/* FEAT-39 (Stef 2026-07-22): the APWorld index browser is public.
            The backing list + download APIs never required a session; the
            community index is part of the site's public catalog and the
            guides link to it. Note for FEAT-38: when the /apworlds Create
            YAML buttons land, they must handle anonymous users (their
            backend is session-gated). */}
        <NavLink to="/apworlds">APWorlds</NavLink>
        <NavLink to="/yaml-builder">YAML Builder</NavLink>
        {user && <NavLink to="/my/yamls">My</NavLink>}
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
 *   - signed-in room host: redirect to /rooms when approved or open access is on
 *   - anonymous visitor, or pending user while open access is off: Landing
 *     (marketing + Discord CTA and, when applicable, the legacy beta notice)
 */
function HomeView() {
  const { user, authEnabled, loading } = useAuth();
  const openRoomCreation = useFeature("open_room_creation");
  if (loading) return null;
  if (!authEnabled) return <GameList />;
  if (user?.is_admin) return <GameList />;
  if (user?.is_approved || (user && openRoomCreation)) return <Navigate to="/rooms" replace />;
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

function RequireRoomAccess({ children }: { children: React.ReactNode }) {
  const { user, authEnabled, loading } = useAuth();
  const openRoomCreation = useFeature("open_room_creation");
  if (loading) return null;
  if (!authEnabled) return <>{children}</>;
  if (!user) return <Navigate to="/" replace />;
  if (!user.is_approved && !user.is_admin && !openRoomCreation) return <Navigate to="/" replace />;
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
      <DeploymentBanner />
      <NavBar />
      <ApprovalToast />
      {/* The boundary sits inside the shell so a lazy route chunk loads with
          the banner and nav already on screen instead of blanking the page. */}
      <main className="container"><Suspense fallback={<RouteChunkFallback />}>{children}</Suspense></main>
    </>
  );
}

function RouteChunkFallback() {
  return <p className="loading">Loading...</p>;
}

/**
 * FEAT-31: record which SPA view is on screen.
 *
 * The backend serves the same index.html for every client route, so this is
 * the only place a view can be identified. A coarse view NAME is sent, never
 * the URL: room ids, seeds and query strings stay out of the analytics log.
 */
function RouteAnalytics() {
  const location = useLocation();
  useEffect(() => {
    const p = location.pathname;
    let view = "other";
    if (p === "/") view = "landing";
    else if (p === "/apworlds") view = "apworlds";
    else if (p === "/yaml-builder" || p.startsWith("/yaml-builder/")) view = "yaml_builder";
    else if (p === "/rooms") view = "rooms";
    else if (p === "/rooms/templates") view = "room_templates";
    else if (p.startsWith("/my")) view = "my_area";
    else if (p.startsWith("/rooms/")) view = "room_detail";
    else if (p.startsWith("/r/")) view = "room_public";
    else if (p.startsWith("/play/")) view = "play";
    else if (p.startsWith("/admin")) view = "admin";
    else if (p.startsWith("/market")) view = "market";
    else if (p.startsWith("/games/")) view = "game_detail";
    else if (p === "/tracker") view = "tracker";
    else if (p === "/servers") view = "servers";
    else if (p === "/summary") view = "summary";
    trackPageView(view);
  }, [location.pathname]);
  return null;
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
      <Route path="/admin/apworld-requests" element={<AdminShell><RequireAdmin><AdminApworldRequests /></RequireAdmin></AdminShell>} />
      <Route path="/" element={<AdminShell><HomeView /></AdminShell>} />
      <Route path="/rooms" element={<AdminShell><RequireRoomAccess><Rooms /></RequireRoomAccess></AdminShell>} />
      <Route path="/rooms/:id" element={<AdminShell><RequireRoomAccess><RoomDetail /></RequireRoomAccess></AdminShell>} />
      <Route path="/tracker" element={<AdminShell><RequireApproval><TrackerPage /></RequireApproval></AdminShell>} />
      <Route path="/games/:seed" element={<AdminShell><RequireApproval><GameDetail /></RequireApproval></AdminShell>} />
      <Route path="/games/:seed/market" element={<AdminShell><RequireApproval><Market /></RequireApproval></AdminShell>} />
      <Route path="/servers" element={<AdminShell><RequireApproval><Servers /></RequireApproval></AdminShell>} />
      <Route path="/apworlds" element={<AdminShell><APWorlds /></AdminShell>} />
      <Route path="/apworlds/:slug" element={<AdminShell><APWorldDetailPreview /></AdminShell>} />
      <Route path="/style-guide" element={<AdminShell><StyleGuide /></AdminShell>} />
      <Route path="/yaml-builder" element={<AdminShell><YamlBuilderLanding /></AdminShell>} />
      <Route path="/yaml-builder/:apworld" element={<AdminShell><YamlBuilderPage /></AdminShell>} />
      <Route path="/rooms/templates" element={<Navigate to="/my/templates" replace />} />
      {/* FEAT-43: one personal area. The old single-purpose paths redirect
          so existing links and bookmarks keep working. */}
      <Route path="/my" element={<Navigate to="/my/yamls" replace />} />
      <Route path="/my/:tab" element={<AdminShell><MyArea /></AdminShell>} />
      <Route path="/account-recovery" element={<AdminShell><AccountRecovery /></AdminShell>} />
      <Route path="/presets" element={<Navigate to="/my/presets" replace />} />
      <Route path="/summary" element={<AdminShell><RequireApproval><Summary /></RequireApproval></AdminShell>} />
      <Route path="*" element={<AdminShell><NotFound /></AdminShell>} />
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
        <DeploymentProvider>
          <BrowserRouter>
            <PublicRouteHead />
            <RouteAnalytics />
            {/* Outer boundary for the public routes, which render through
                PublicLayout rather than AdminShell. */}
            <Suspense fallback={<RouteChunkFallback />}>
              <AppRoutes />
            </Suspense>
          </BrowserRouter>
        </DeploymentProvider>
      </FeaturesProvider>
    </AuthProvider>
  );
}

export default App;
