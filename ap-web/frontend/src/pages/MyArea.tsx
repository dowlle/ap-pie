import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import {
  deleteMyYaml,
  getMySubmissions,
  getMyYamls,
  updateMyYaml,
  getMyRooms,
  type MyRoom,
  type UserSubmission,
  type UserYaml,
} from "../api";
import { useAuth } from "../context/AuthContext";
import { useFeature } from "../context/FeaturesContext";
import { usePageTitle } from "../lib/usePageTitle";
import MyPresets from "./MyPresets";
import MyRoomTemplates from "./MyRoomTemplates";
import AccountTab from "./AccountTab";
import MyFavoriteGames from "./MyFavoriteGames";
import MyJoinedRooms from "./MyJoinedRooms";
import { downloadYaml } from "../lib/yamlBuild";

/**
 * FEAT-43: one personal area instead of three scattered "my" pages.
 *
 * Before this, `/rooms/templates` and `/presets` were reachable from two
 * different page headers and a third personal library was about to appear.
 * More importantly there was no object called "my YAML" anywhere in the
 * product: a submission lived inside one room, a preset was a configuration
 * without a slot name, and hand-edited text lived nowhere at all. That
 * absence is why version drift and option warnings had nothing to attach to.
 *
 * Tabs are routed (`/my/yamls`) rather than held in state, so a link points
 * at a specific tab and the back button behaves.
 */

const TABS = [
  { key: "rooms", label: "Rooms" },
  { key: "favorites", label: "Favorite games" },
  { key: "yamls", label: "YAMLs" },
  { key: "presets", label: "Presets" },
  { key: "templates", label: "Room templates" },
  { key: "account", label: "Account" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function MyArea() {
  const { tab } = useParams<{ tab?: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const openRoomCreation = useFeature("open_room_creation");
  const isApproved = !!(user?.is_approved || user?.is_admin);
  const isKnownTab = TABS.some((t) => t.key === tab);
  const active: TabKey = isKnownTab ? (tab as TabKey) : "yamls";
  usePageTitle(`My ${active === "yamls" ? "YAMLs" : active}`);

  const visibleTabs = useMemo(
    // Room templates are a host tool; there is nothing behind that tab for
    // an account that cannot create rooms yet. Hiding the tab beats gating
    // the whole area.
    () => TABS.filter((t) => t.key !== "templates" || isApproved || openRoomCreation),
    [isApproved, openRoomCreation],
  );

  if (tab && !isKnownTab) return <Navigate to="/my/yamls" replace />;
  if (active === "templates" && !isApproved && !openRoomCreation) {
    return <Navigate to="/my/yamls" replace />;
  }

  if (!user) {
    return (
      <div>
        <h1>My stuff</h1>
        <p className="muted">
          <a href="/api/auth/login?next=/my/yamls">Sign in with Discord</a> to keep
          a library of your YAMLs, save presets, and see everything you have
          submitted across rooms.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>My stuff</h1>
      <div className="my-tabs">
        {visibleTabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`my-tab ${active === t.key ? "is-active" : ""}`}
            onClick={() => navigate(`/my/${t.key}`)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {active === "yamls" && <MyYamlsTab />}
      {active === "favorites" && <MyFavoriteGames />}
      {active === "rooms" && <MyJoinedRooms />}
      {active === "presets" && <MyPresets embedded />}
      {active === "templates" && (isApproved || openRoomCreation) && <MyRoomTemplates embedded />}
      {active === "account" && <AccountTab />}
    </div>
  );
}

function MyYamlsTab() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [yamls, setYamls] = useState<UserYaml[]>([]);
  const [submissions, setSubmissions] = useState<UserSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rooms, setRooms] = useState<MyRoom[]>([]);
  const [pendingRemoval, setPendingRemoval] = useState<UserYaml | null>(null);
  const [sending, setSending] = useState<UserYaml | null>(null);
  const [destination, setDestination] = useState("");
  const [loadedAt] = useState(() => Date.now());
  const drafts = Object.keys(sessionStorage).filter(key => key.startsWith(`ap-pie:yaml-builder:${user?.id}:`));

  useEffect(() => {
    Promise.all([getMyYamls(), getMySubmissions(), getMyRooms()])
      .then(([y, s, r]) => { setYamls(y); setSubmissions(s); setRooms(r); })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const openInBuilder = (y: UserYaml) => {
    navigate(`/yaml-builder/${encodeURIComponent(y.apworld_name)}` +
      `?version=${encodeURIComponent(y.version)}&from=${y.id}`);
  };

  const remove = async (y: UserYaml) => {
    try {
      await deleteMyYaml(y.id);
      setPendingRemoval(null);
      setYamls((prev) => prev.filter((x) => x.id !== y.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const rename = async (y: UserYaml, label: string) => {
    try {
      const updated = await updateMyYaml(y.id, { label });
      setYamls((prev) => prev.map((x) => (x.id === y.id ? updated : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to rename");
    }
  };

  if (loading) return <p className="loading">Loading...</p>;

  return (
    <>
      {error && <p className="error">{error}</p>}
      <section className="settings-section">
        <h2>Continue where you left off</h2>
        <p>Saved YAMLs are available on any device after sign-in. Browser-tab drafts stay on this device.</p>
        {drafts.length > 0 && <p><Link to="/yaml-builder">Continue a browser-tab draft</Link> ({drafts.length})</p>}
        {submissions.some(s => s.validation_status === "failed" || !!s.option_warnings?.length) && <p><a href="#yaml-submissions">Review submissions needing attention</a></p>}
        {[...rooms].filter(room => room.status === "open" && room.submit_deadline).sort((a, b) => a.submit_deadline!.localeCompare(b.submit_deadline!)).slice(0, 3).map(room => <p key={room.id}><Link to={`/r/${room.id}`}>{room.name}</Link> · Submit by {new Date(room.submit_deadline!).toLocaleString()}</p>)}
        <Link className="btn" to="/yaml-builder">Prepare another YAML</Link>
      </section>
      {pendingRemoval && <section className="settings-section" role="status">
        <p>Delete “{pendingRemoval.label || pendingRemoval.apworld_name}”? Your room submissions will remain.</p>
        <button className="btn" onClick={() => setPendingRemoval(null)}>Keep this YAML</button>
        <button className="btn btn-danger" onClick={() => void remove(pendingRemoval)}>Delete permanently</button>
      </section>}
      {sending && <section className="settings-section">
        <h3>Send {sending.label || sending.apworld_name} to a room</h3>
        <p>Your saved original stays unchanged. Review the room's required version before submitting.</p>
        <select aria-label="Destination room" value={destination} onChange={event => setDestination(event.target.value)}>
          <option value="">Select an open room…</option>
          {rooms.filter(room => room.status === "open" && (!room.submit_deadline || Date.parse(room.submit_deadline) > loadedAt)).map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
        </select>
        <button className="btn btn-primary" disabled={!destination} onClick={() => navigate(`/yaml-builder/${encodeURIComponent(sending.apworld_name)}?context=public-room&room=${encodeURIComponent(destination)}&from=${sending.id}`)}>Review and submit</button>
        <button className="btn" onClick={() => setSending(null)}>Cancel</button>
        <p>Missing a room? Open its invitation and join it first.</p>
      </section>}

      <section className="settings-section">
        <h3>Saved</h3>
        {yamls.length === 0 ? (
          <p className="settings-hint" style={{ margin: 0 }}>
            Nothing saved yet. Build a YAML from the{" "}
            <Link to="/apworlds">APWorlds page</Link> and choose "Save to my
            YAMLs" on the review step. Saved YAMLs can be reopened in the
            builder, reused in another room, and are checked against new
            versions of the game as they land.
          </p>
        ) : (
          <ul className="my-yaml-list">
            {yamls.map((y) => (
              <li key={y.id} className="my-yaml-row">
                <div className="my-yaml-text">
                  <div className="my-yaml-head">
                    <strong>{y.label || y.apworld_name}</strong>
                    <code className="apworld-card-key">{y.apworld_name}</code>
                    <span className="badge">{y.kind === "advanced" ? "file" : "config"}</span>
                    {y.outdated && (
                      <span
                        className="badge badge-stopped"
                        title={`Saved against v${y.version}; the index now has v${y.latest_version}`}
                      >
                        v{y.version} → v{y.latest_version}
                      </span>
                    )}
                  </div>
                  <p className="my-yaml-meta">
                    slot "{y.player_name}"
                    {y.kind === "simple" && y.values &&
                      ` · ${Object.keys(y.values).length} option${
                        Object.keys(y.values).length === 1 ? "" : "s"
                      }`}
                    {y.warnings.length > 0 && (
                      <span className="my-yaml-warn">
                        {" · "}⚠ {y.warnings.length} option
                        {y.warnings.length === 1 ? "" : "s"} no longer valid
                      </span>
                    )}
                  </p>
                  {y.warnings.length > 0 && (
                    <ul className="my-yaml-warnings">
                      {y.warnings.slice(0, 3).map((w) => (
                        <li key={w.option}>{w.detail}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="my-yaml-actions">
                  <button type="button" className="btn btn-sm" onClick={() => openInBuilder(y)}>
                    {y.outdated ? `Keep v${y.version}` : "Open in builder"}
                  </button>
                  {y.outdated && <button className="btn btn-sm" onClick={() => navigate(`/yaml-builder/${encodeURIComponent(y.apworld_name)}?version=${encodeURIComponent(y.latest_version!)}&from=${y.id}`)}>Review v{y.latest_version} changes</button>}
                  <button className="btn btn-sm" onClick={() => { setSending(y); setDestination(""); }}>Send to room</button>
                  {y.kind === "advanced" && y.yaml_content && <button className="btn btn-sm" onClick={() => downloadYaml(y.yaml_content!, y.player_name, y.apworld_name)}>Download saved file</button>}
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => {
                      const next = window.prompt("Name this YAML", y.label || y.apworld_name);
                      if (next !== null) void rename(y, next);
                    }}
                  >
                    Rename
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setPendingRemoval(y)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section id="yaml-submissions" className="settings-section" style={{ marginTop: "1.25rem" }}>
        <h3>Submitted</h3>
        <p className="settings-hint">
          Everything this account has submitted, across every room. Anything
          submitted without signing in is not listed here, because there is no
          account it belongs to.
        </p>
        {submissions.length === 0 ? (
          <p className="settings-hint" style={{ margin: 0 }}>No submissions yet.</p>
        ) : (
          <ul className="my-yaml-list">
            {[...submissions].sort((a, b) => Number(b.validation_status === "failed" || !!b.option_warnings?.length) - Number(a.validation_status === "failed" || !!a.option_warnings?.length)).map((s) => (
              <li key={s.id} className="my-yaml-row">
                <div className="my-yaml-text">
                  <div className="my-yaml-head">
                    <strong>{s.game}</strong>
                    <span className="badge">{s.room_status}</span>
                    {s.validation_status === "failed" && (
                      <span className="badge badge-stopped">invalid</span>
                    )}
                    {(s.option_warnings?.length ?? 0) > 0 && (
                      <span className="badge badge-save">
                        ⚠ {s.option_warnings!.length}
                      </span>
                    )}
                  </div>
                  <p className="my-yaml-meta">
                    slot "{s.player_name}" in{" "}
                    <Link to={`/r/${s.room_id}`}>{s.room_name}</Link>
                  </p>
                  {s.validation_error && (
                    <p className="my-yaml-warn">{s.validation_error}</p>
                  )}
                  {(s.option_warnings ?? []).slice(0, 3).map((w) => (
                    <p key={w.option} className="my-yaml-warn">{w.detail}</p>
                  ))}
                </div>
                <div className="my-yaml-actions">
                  <Link className="btn btn-sm" to={`/r/${s.room_id}`}>{s.validation_status === "failed" || s.option_warnings?.length ? "Open room to review and edit" : "Open room"}</Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
