import { useEffect, useRef, useState } from "react";
import {
  getRoomActivityStream,
  getPublicRoomActivityStream,
  type ActivityEvent,
} from "../api";

/**
 * FEAT-17 V1.5: live in-game activity feed.
 *
 * Polls `/api/rooms/<id>/activity-stream` every POLL_MS - the server
 * returns the bounded ring buffer of PrintJSON events from its WebSocket
 * tracker connection. We hand back `now` as `?since=` on the next poll
 * so we only ship deltas after the first request.
 *
 * Renders nothing when the WS subsystem isn't connected for this room
 * (`status: "no_connection"`) - avoids planting an empty panel under the
 * grid when Archipelago Pie isn't actively tracking. Once a connection comes up,
 * the next poll makes the feed appear automatically.
 */

const POLL_MS = 10_000;
// Cap rendered events. Server sends up to 200 in the buffer; rendering
// them all is fine for performance but visually noisy. Most-recent-first.
const MAX_RENDERED = 100;

const TYPE_ICONS: Record<string, string> = {
  ItemSend: "\u{1F4E6}",   // 📦
  Hint: "\u{1F4A1}",        // 💡
  Goal: "\u{1F3C1}",        // 🏁
  Chat: "\u{1F4AC}",        // 💬
  Join: "\u{1F44B}",        // 👋
  Part: "\u{1F6AA}",        // 🚪
  Tutorial: "\u{1F4D6}",   // 📖
  Release: "\u{1F4E4}",    // 📤
  Collect: "\u{1F4E5}",    // 📥
  Tags: "\u{1F3F7}",       // 🏷
  CommandResult: "\u{27A1}", // ➡
};

function iconFor(type: string): string {
  return TYPE_ICONS[type] ?? "\u{2022}"; // bullet
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString();
}

export default function ActivityFeed({
  roomId,
  publicMode = false,
}: {
  roomId: string;
  publicMode?: boolean;
}) {
  // Server status - drives the "WS not connected" empty state. Distinct
  // from `events.length` because the buffer can be empty even on a live
  // connection (quiet room).
  const [status, setStatus] = useState<string | null>(null);
  // Full event ring as we've seen it; we append deltas from each poll.
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [filter, setFilter] = useState<string>("");
  const sinceRef = useRef<number | undefined>(undefined);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    sinceRef.current = undefined;
    setEvents([]);
    setStatus(null);

    const tick = async () => {
      try {
        const fetcher = publicMode
          ? getPublicRoomActivityStream(roomId, sinceRef.current)
          : getRoomActivityStream(roomId, sinceRef.current);
        const r = await fetcher;
        if (cancelled) return;
        setStatus(r.status);
        if (r.now !== undefined) sinceRef.current = r.now;
        if (r.events && r.events.length > 0) {
          // Append new events. Server returns them in chronological order.
          setEvents((prev) => {
            const combined = [...prev, ...r.events];
            // Trim from the front so we never grow unbounded; renderer
            // shows the most recent MAX_RENDERED.
            const cap = MAX_RENDERED * 2;
            if (combined.length > cap) return combined.slice(combined.length - cap);
            return combined;
          });
        }
      } catch {
        // Silent - the next tick retries. Don't flicker the UI on
        // transient network blips.
      }
    };

    void tick();
    intervalRef.current = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [roomId, publicMode]);

  // V1.5 design choice: hide the whole panel when WS isn't connected.
  // Avoids a confusing "Activity (empty)" placeholder under the grid for
  // rooms that don't have FEAT-17 connectivity (e.g. capped-out, no
  // tracker URL, or behind the AP_TRACKER_WS_ENABLED flag being off).
  if (status === null) return null; // still loading first response
  if (status === "no_connection") return null;

  // Most-recent-first, optionally filtered by type or text substring.
  const filterLower = filter.trim().toLowerCase();
  const visible = events
    .slice()
    .reverse()
    .filter((e) => {
      if (!filterLower) return true;
      return (
        e.type.toLowerCase().includes(filterLower) ||
        (e.text || "").toLowerCase().includes(filterLower)
      );
    })
    .slice(0, MAX_RENDERED);

  return (
    <div className="activity-feed">
      <div className="activity-feed-header">
        <h4 className="activity-feed-title">Live activity</h4>
        <span className="muted activity-feed-meta">
          {events.length} event{events.length === 1 ? "" : "s"} ·
          updates every {POLL_MS / 1000}s
        </span>
        {events.length > 0 && (
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter activity…"
            aria-label="Filter activity events"
            className="yaml-search activity-feed-search"
          />
        )}
      </div>
      {visible.length === 0 ? (
        <p className="muted activity-feed-empty">
          {events.length === 0
            ? "Waiting for the first event from the AP server…"
            : "No events match that filter."}
        </p>
      ) : (
        <ul className="activity-feed-list">
          {visible.map((e, i) => (
            <li key={`${e.ts}-${i}`} className={`activity-feed-item activity-${e.type.toLowerCase()}`}>
              <span className="activity-feed-icon" aria-hidden="true">{iconFor(e.type)}</span>
              <span className="activity-feed-time muted">{formatTime(e.ts)}</span>
              <span className="activity-feed-type">{e.type}</span>
              <span className="activity-feed-text">{e.text || <em className="muted">(no text)</em>}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
