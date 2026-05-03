import { useEffect, useState, useRef } from "react";
import { getRoomTracker, getPublicRoomTracker, type RoomTrackerData, type PlayerInfo } from "../api";
import {
  filterAndSortPlayers,
  nextTrackerSort,
  trackerSortIndicator,
  trackerSortPressed,
  type TrackerSort,
  type TrackerSortKey,
} from "../lib/trackerGrid";
import SlotDetailModal from "./SlotDetailModal";
import ActivityFeed from "./ActivityFeed";
import { useAuth } from "../context/AuthContext";

function statusIcon(label: string) {
  if (label === "goal") return "\u{1F7E2}";
  if (label === "playing") return "\u{1F7E2}";
  if (label === "connected" || label === "ready") return "\u{1F7E1}";
  return "\u26AA";
}

function barColor(pct: number): string {
  if (pct >= 75) return "var(--green)";
  if (pct >= 25) return "var(--yellow)";
  return "var(--accent)";
}

function PlayerCard({
  player,
  onClick,
}: {
  player: PlayerInfo;
  /** When set, the card becomes clickable (FEAT-14 modal). When omitted,
   *  renders as a static div for tracker sources that don't yet support
   *  per-slot detail. */
  onClick?: (p: PlayerInfo) => void;
}) {
  const className = `tracker-card${player.goal_completed ? " tracker-card-completed" : ""}${onClick ? " tracker-card-clickable" : ""}`;
  const inner = (
    <>
      <div className="tracker-card-name">{player.name}</div>
      <div className="tracker-card-game">{player.game}</div>
      <div className="completion-bar">
        <div
          className="completion-fill"
          style={{ width: `${player.completion_pct}%`, background: barColor(player.completion_pct) }}
        />
        <span className="completion-text">{player.completion_pct}%</span>
      </div>
      <div className="tracker-card-checks">
        {player.checks_done} / {player.checks_total} checks
      </div>
      <div className="tracker-card-status">
        {statusIcon(player.status_label)} {player.status_label}
      </div>
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        className={className}
        onClick={() => onClick(player)}
        aria-label={`Open detail for ${player.name} (${player.game})`}
      >
        {inner}
      </button>
    );
  }
  return <div className={className}>{inner}</div>;
}

function fixConnectionUrl(url: string): string {
  if (url.startsWith("localhost:")) {
    return url.replace("localhost", window.location.hostname);
  }
  return url;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button className="btn btn-sm copy-btn" onClick={handleCopy}>
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default function LiveTracker({
  roomId,
  publicMode = false,
}: {
  roomId: string;
  /** FEAT-08: when true, calls the public tracker endpoint (no auth, returns
   *  external-only). RoomPublic uses this; RoomDetail (host) leaves it false. */
  publicMode?: boolean;
}) {
  const [data, setData] = useState<RoomTrackerData | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<number | null>(null);
  // UX-09: search + sort state. Default sort is null (preserves backend
  // ordering), which keeps existing behaviour for users who don't interact.
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<TrackerSort | null>(null);
  const toggleSort = (key: TrackerSortKey) => setSort((cur) => nextTrackerSort(cur, key));
  // FEAT-14: which slot's detail modal is open, if any.
  const [openPlayer, setOpenPlayer] = useState<PlayerInfo | null>(null);
  const { user } = useAuth();

  const fetchTracker = () => {
    const fetcher = publicMode ? getPublicRoomTracker(roomId) : getRoomTracker(roomId);
    fetcher
      .then((d) => {
        // The public endpoint returns {status: "no_tracker"} when the room has
        // no tracker_url set - treat as "no data" to avoid rendering an empty
        // dashboard on the lobby.
        if ((d as { status?: string }).status === "no_tracker") {
          setData(null);
        } else {
          setData(d as RoomTrackerData);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchTracker();
    intervalRef.current = window.setInterval(fetchTracker, 15000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [roomId, publicMode]);

  if (loading) return <p className="loading">Loading tracker...</p>;
  if (!data) return null;

  if (data.status === "not_generated") {
    return <p className="muted">Game has not been generated yet.</p>;
  }
  if ((data as { status?: string }).status === "external_error") {
    const err = (data as { error?: string }).error;
    return (
      <p className="muted">
        Couldn't fetch the external tracker
        {err ? <>: <code>{err}</code></> : null}.
      </p>
    );
  }

  const serverStopped = data.server_status !== "running";
  // UX-09: derived after the data guard above so the helper sees a real array.
  const displayedPlayers = filterAndSortPlayers(data.players, search, sort);
  // FEAT-08: external trackers (archipelago.gg) only expose slot/name/game,
  // not per-slot checks or items. Surface a small note so the empty bars
  // aren't mistaken for "the game hasn't started yet".
  // FEAT-17 V1.4: source is "external+ws" when the WebSocket tracker is
  // connected and overlaying live status data on top of the HTML scrape.
  const source = (data as { source?: string }).source;
  const isExternal = source === "external" || source === "external+ws";
  const isLiveTracked = source === "external+ws";
  const externalTrackerUrl = (data as { tracker_url?: string }).tracker_url;
  const noChecksData = data.total_checks_total === 0;

  return (
    <div className="tracker-panel">
      {/* Connection bar */}
      <div className="tracker-connection">
        {data.connection_url ? (
          <>
            <span className="tracker-connect-label">Connect:</span>
            <code className="connection-url">{fixConnectionUrl(data.connection_url)}</code>
            <CopyButton text={fixConnectionUrl(data.connection_url)} />
          </>
        ) : isExternal && externalTrackerUrl ? (
          <a
            href={externalTrackerUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tracker-connect-label"
          >
            View on external tracker ↗
          </a>
        ) : (
          <span className="muted">Server is not running</span>
        )}
        <span className="tracker-refresh-hint">
          {serverStopped ? "last known state" : "auto-refreshes every 15s"}
        </span>
        {isLiveTracked && (
          <span className="tracker-live-badge" title="WebSocket connection to the AP server is active. Status, hints and activity update in real time.">
            ● live
          </span>
        )}
      </div>

      {/* Summary bar */}
      <div className="tracker-summary">
        <div className="completion-bar completion-bar-lg" style={{ flex: 1 }}>
          <div
            className="completion-fill"
            style={{ width: `${data.overall_completion_pct}%`, background: barColor(data.overall_completion_pct) }}
          />
          <span className="completion-text">
            {data.total_checks_done} / {data.total_checks_total} checks ({data.overall_completion_pct}%)
          </span>
        </div>
        <div className="tracker-goals">
          {data.goals_completed} / {data.goals_total} goals
          {data.all_goals_completed && <span className="badge badge-done" style={{ marginLeft: "0.5rem" }}>Complete!</span>}
        </div>
      </div>

      {/* UX-09: search + sort toolbar. Hidden when there are 0 players so it
          doesn't clutter pre-game / no-data states. */}
      {data.players.length > 0 && (
        <div className="tracker-toolbar">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search player or game…"
            aria-label="Search players"
            className="yaml-search tracker-search"
          />
          <div className="tracker-sort-row" role="group" aria-label="Sort players by">
            <span className="tracker-sort-label muted">Sort:</span>
            {(
              [
                ["completion", "Completion"],
                ["status", "Status"],
                ["name", "Name"],
                ["game", "Game"],
                ["checks", "Checks"],
              ] as Array<[TrackerSortKey, string]>
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`tracker-sort-chip${trackerSortPressed(sort, key) ? " is-active" : ""}`}
                onClick={() => toggleSort(key)}
                aria-pressed={trackerSortPressed(sort, key)}
              >
                {label}{trackerSortIndicator(sort, key)}
              </button>
            ))}
          </div>
          {(search.trim() || sort) && (
            <span className="muted yaml-count tracker-count">
              {displayedPlayers.length} of {data.players.length}
            </span>
          )}
        </div>
      )}

      {/* Player cards. FEAT-14: cards are clickable only when the data
          source is external (archipelago.gg) - that's the only path
          fetch_slot_data knows how to scrape today. Local-seed rooms
          fall back to non-clickable cards. */}
      <div className="tracker-grid">
        {displayedPlayers.map((p) => (
          <PlayerCard
            key={p.slot}
            player={p}
            onClick={isExternal ? setOpenPlayer : undefined}
          />
        ))}
      </div>

      {openPlayer && (
        <SlotDetailModal
          roomId={roomId}
          player={openPlayer}
          publicMode={publicMode}
          viewerUserId={user?.id ?? null}
          onClose={() => setOpenPlayer(null)}
        />
      )}
      {data.players.length > 0 && displayedPlayers.length === 0 && (
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          No players match &ldquo;{search}&rdquo;.
        </p>
      )}

      {!data.has_save && !isExternal && (
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          No save data yet - progress will appear once players connect.
        </p>
      )}
      {isExternal && noChecksData && data.players.length === 0 && (
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          External tracker returned no players yet - either the room hasn't
          accepted any connections or the URL doesn't match an archipelago.gg
          tracker we can parse.
        </p>
      )}
      {isExternal && data.players.length > 0 && !isLiveTracked && (
        <p className="muted" style={{ marginTop: "0.5rem" }}>
          Per-slot items aren't shown - archipelago.gg's tracker page
          only exposes the per-player checks roll-up. Click any slot to see
          received items, locations and hints scraped on demand.
        </p>
      )}

      {/* FEAT-17 V1.5: in-game activity feed. Renders only when the
          WebSocket tracker is connected for this room (component
          self-hides on no_connection). */}
      <ActivityFeed roomId={roomId} publicMode={publicMode} />
    </div>
  );
}
