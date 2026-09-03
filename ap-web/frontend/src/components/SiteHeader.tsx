import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { refreshData } from "../api";
import { useAuth } from "../context/AuthContext";
import { useFeature } from "../context/FeaturesContext";
import AuthButton from "./AuthButton";

/** One navigation model for every SPA shell. Public pages no longer carry a
 * separate header with different destinations. Role and feature checks only
 * add capabilities; the public orientation links remain stable. */
export default function SiteHeader() {
  const { user, authEnabled, loading, isOwner, viewAs, setViewAs } = useAuth();
  const generationOn = useFeature("generation");
  const openRoomCreation = useFeature("open_room_creation");
  const [menuOpen, setMenuOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const isAdmin = !!user?.is_admin;
  const isApproved = !!(user?.is_approved || user?.is_admin);
  const canUseRooms = !!user && (isApproved || openRoomCreation);
  const authBypassed = !authEnabled || loading;
  const showRoomsLink = authBypassed || canUseRooms;
  const showAdminTools = authBypassed || isAdmin;

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshData();
      window.location.reload();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <nav className="navbar" aria-label="Main navigation">
      <Link to="/" className="nav-brand" onClick={() => setMenuOpen(false)}>
        Archipelago Pie
      </Link>
      <button
        type="button"
        className="nav-hamburger"
        aria-expanded={menuOpen}
        aria-controls="nav-drawer"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        onClick={() => setMenuOpen((open) => !open)}
      >
        <span className="nav-hamburger-bar" />
        <span className="nav-hamburger-bar" />
        <span className="nav-hamburger-bar" />
      </button>
      <div
        id="nav-drawer"
        className="nav-links"
        data-open={menuOpen ? "true" : undefined}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a, button")) setMenuOpen(false);
        }}
      >
        <NavLink to="/apworlds">APWorlds</NavLink>
        <NavLink to="/yaml-builder">YAML Builder</NavLink>
        <a href="/guides">Guides</a>
        {showRoomsLink && <NavLink to="/rooms">Rooms</NavLink>}
        {user && <NavLink to="/my/yamls">My</NavLink>}
        {showAdminTools && generationOn && (
          <>
            <NavLink to="/tracker">Tracker</NavLink>
            <NavLink to="/" end>Games</NavLink>
            <NavLink to="/servers">Servers</NavLink>
            <NavLink to="/summary">Summary</NavLink>
            <button onClick={handleRefresh} disabled={refreshing} className="btn btn-sm">
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </>
        )}
        {user?.is_admin && <NavLink to="/admin">Admin</NavLink>}
        {isOwner && (
          <label
            className="view-as-toggle"
            title="Preview the interface as another role. Backend permissions are unchanged."
          >
            <span className="view-as-label">View as</span>
            <select
              value={viewAs}
              onChange={(event) => setViewAs(event.target.value as "admin" | "host" | "user")}
            >
              <option value="admin">Admin</option>
              <option value="host">Host</option>
              <option value="user">User</option>
            </select>
          </label>
        )}
        <AuthButton />
      </div>
    </nav>
  );
}
