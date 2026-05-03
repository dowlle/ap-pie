import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * Wrapper for the no-auth public surfaces (/r/<id> and /play/<seed>).
 *
 * The full admin nav (Market, Tracker, Games, Servers, APWorlds, Summary,
 * Refresh) is overkill for a player who clicked a Discord link from a
 * friend. They came for ONE room or ONE seed; the page should make that
 * obvious. Login/logout, however, belongs everywhere - a Discord-gated
 * room (room.require_discord_login) needs the visitor to authenticate,
 * and a logged-in submitter wants to see who they are and be able to
 * sign out. So this shell carries a slim auth control on the right of
 * the header alongside the brand mark.
 */
function PublicAuthControl() {
  const { user, isAuthenticated, authEnabled, loading, login, logout } = useAuth();
  const location = useLocation();
  if (loading || !authEnabled) return null;
  if (!isAuthenticated) {
    return (
      <button
        type="button"
        className="btn btn-sm btn-primary"
        onClick={() => login(location.pathname)}
      >
        Login with Discord
      </button>
    );
  }
  return (
    <div className="public-shell-auth">
      <span className="muted public-shell-auth-name" title={`Signed in as ${user?.discord_username}`}>
        {user?.discord_username}
      </span>
      <button type="button" className="btn btn-sm" onClick={logout}>
        Logout
      </button>
    </div>
  );
}

export default function PublicLayout() {
  return (
    <div className="public-shell">
      <header className="public-shell-header">
        <Link to="/" className="public-shell-brand" title="Archipelago Pie home">
          <span className="public-shell-brand-mark" aria-hidden="true" />
          <span>Archipelago Pie</span>
        </Link>
        <PublicAuthControl />
      </header>
      <main className="public-shell-main">
        <Outlet />
      </main>
    </div>
  );
}
