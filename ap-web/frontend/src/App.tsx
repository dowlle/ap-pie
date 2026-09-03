import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
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
const RoomWorkspace = lazy(() => import("./pages/RoomWorkspace"));
const LegacyRoomRedirect = lazy(() => import("./pages/RoomWorkspace").then((module) => ({ default: module.LegacyRoomRedirect })));
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
import { AuthProvider, useAuth } from "./context/AuthContext";
import { FeaturesProvider, useFeature } from "./context/FeaturesContext";
import { DeploymentProvider } from "./context/DeploymentContext";
import DeploymentBanner from "./components/DeploymentBanner";
import SiteHeader from "./components/SiteHeader";
import { trackPageView } from "./lib/analytics";
import PublicRouteHead from "./lib/PublicRouteHead";

/**
 * The `/` landing decides per audience:
 *   - dev mode (auth disabled) or admin: legacy GameList (admin tooling)
 *   - signed-in room host: redirect to /rooms when approved or open access is on
 *   - anonymous visitor, or pending user while open access is off: Landing
 *     (marketing + Discord CTA and, when applicable, the legacy beta notice)
 */
function HomeView() {
  const { authEnabled, loading } = useAuth();
  if (loading) return null;
  // Local development with auth disabled keeps the operator view at the root.
  if (!authEnabled) return <GameList />;
  // Everyone signed in gets the landing page, admins included. It used to
  // redirect members to /rooms and hand admins the generated-games list, so
  // neither could reach the homepage. The generated-games list now lives at
  // /games, and Landing swaps its sign-in calls to action for links into the
  // viewer's own rooms.
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
 * Renders the application canvas and approval toast. PublicLayout shares the
 * same header but uses the room-oriented public canvas.
 */
function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <DeploymentBanner />
      <SiteHeader />
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
      {/* Public routes use the shared header and privacy-filtered loaders. */}
      <Route element={<PublicLayout />}>
        <Route path="/play/:seed" element={<Play />} />
        <Route path="/r/:id" element={<RoomWorkspace />} />
      </Route>

      {/* Application and compatibility routes. */}
      <Route path="/market" element={<AdminShell><MarketLanding /></AdminShell>} />
      <Route path="/market/:trackerId" element={<AdminShell><MarketTracker /></AdminShell>} />
      <Route path="/admin" element={<AdminShell><RequireAdmin><Admin /></RequireAdmin></AdminShell>} />
      <Route path="/admin/apworld-requests" element={<AdminShell><RequireAdmin><AdminApworldRequests /></RequireAdmin></AdminShell>} />
      <Route path="/" element={<AdminShell><HomeView /></AdminShell>} />
      <Route path="/games" element={<AdminShell><RequireAdmin><GameList /></RequireAdmin></AdminShell>} />
      <Route path="/rooms" element={<AdminShell><RequireRoomAccess><Rooms /></RequireRoomAccess></AdminShell>} />
      <Route path="/rooms/:id" element={<LegacyRoomRedirect />} />
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
