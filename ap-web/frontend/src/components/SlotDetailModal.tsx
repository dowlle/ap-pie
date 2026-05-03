import { useEffect, useMemo, useRef, useState } from "react";
import {
  getRoomSlotTracker,
  getPublicRoomSlotTracker,
  type SlotDetail,
  type SlotDetailResponse,
  type PlayerInfo,
} from "../api";

/**
 * FEAT-14: per-slot detail modal opened from a click on a tracker card.
 *
 * Native <dialog> for parity with YamlViewerModal / RoomSettingsModal -
 * we get focus trap, Esc-to-close, and ::backdrop styling for free.
 *
 * Tabs: Overview / Items / Locations / Hints. Each tab independently
 * renders its slice of the data; if a slice is empty the tab still
 * shows but with a muted "nothing here yet" line so users don't think
 * the modal is broken.
 *
 * Owner attribution lives in the header - "Submitted by @username", or
 * "This is your slot" when the viewer matches.
 */

type TabKey = "overview" | "items" | "locations" | "hints";

const TABS: Array<[TabKey, string]> = [
  ["overview", "Overview"],
  ["items", "Items received"],
  ["locations", "Locations"],
  ["hints", "Hints"],
];

function isError(r: SlotDetailResponse | null): r is { error: string } {
  return !!r && "error" in r;
}

export default function SlotDetailModal({
  roomId,
  player,
  publicMode,
  viewerUserId,
  onClose,
}: {
  roomId: string;
  player: PlayerInfo;
  /** When true, hits the public endpoint (anonymous-aware attribution). */
  publicMode: boolean;
  /** Logged-in viewer's user id, or null/undefined for anonymous. Used to
   *  flip the attribution label to "This is your slot". */
  viewerUserId?: number | null;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [response, setResponse] = useState<SlotDetailResponse | null>(null);
  const [tab, setTab] = useState<TabKey>("overview");
  const [showOnlyUnchecked, setShowOnlyUnchecked] = useState(false);
  const [showOnlyOpenHints, setShowOnlyOpenHints] = useState(false);
  const [search, setSearch] = useState("");
  const [refreshTick, setRefreshTick] = useState(0);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResponse(null);
    const fetcher = publicMode
      ? getPublicRoomSlotTracker(roomId, player.slot)
      : getRoomSlotTracker(roomId, player.slot);
    fetcher
      .then((r) => {
        if (!cancelled) {
          setResponse(r);
          setLastFetched(new Date());
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setResponse({ error: e instanceof Error ? e.message : "Failed to load slot data" });
        }
      });
    return () => { cancelled = true; };
  }, [roomId, player.slot, publicMode, refreshTick]);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    const onCancel = (e: Event) => { e.preventDefault(); onClose(); };
    dlg.addEventListener("cancel", onCancel);
    return () => {
      dlg.removeEventListener("cancel", onCancel);
      if (dlg.open) dlg.close();
    };
  }, [onClose]);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  const detail: SlotDetail | null = response && !isError(response) ? response : null;

  // Derived: filtered + sorted lists per tab.
  const filteredItems = useMemo(() => {
    if (!detail) return [];
    const term = search.trim().toLowerCase();
    const list = term
      ? detail.items_received.filter((i) => i.item.toLowerCase().includes(term))
      : detail.items_received;
    // Sort by amount desc; "more of this" is the natural reading order.
    return [...list].sort((a, b) => b.amount - a.amount);
  }, [detail, search]);

  const filteredLocations = useMemo(() => {
    if (!detail) return [];
    const term = search.trim().toLowerCase();
    let list = detail.locations;
    if (showOnlyUnchecked) list = list.filter((l) => !l.checked);
    if (term) list = list.filter((l) => l.location.toLowerCase().includes(term));
    return list;
  }, [detail, search, showOnlyUnchecked]);

  const filteredHints = useMemo(() => {
    if (!detail) return [];
    const term = search.trim().toLowerCase();
    let list = detail.hints;
    if (showOnlyOpenHints) list = list.filter((h) => !h.found);
    if (term) {
      list = list.filter(
        (h) =>
          h.item.toLowerCase().includes(term) ||
          h.finder.toLowerCase().includes(term) ||
          h.receiver.toLowerCase().includes(term) ||
          h.location.toLowerCase().includes(term),
      );
    }
    return list;
  }, [detail, search, showOnlyOpenHints]);

  // Reset search when switching tabs - what's relevant on Items
  // ("sword") rarely overlaps with what's relevant on Locations.
  useEffect(() => { setSearch(""); }, [tab]);

  const isYourSlot = !!(
    detail?.submitter_user_id !== undefined &&
    detail?.submitter_user_id !== null &&
    viewerUserId !== undefined &&
    viewerUserId !== null &&
    detail.submitter_user_id === viewerUserId
  );

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="slot-modal">
      <header className="slot-modal-header">
        <div className="slot-modal-title">
          <strong>{player.name}</strong>
          <span className="muted slot-modal-game">{player.game}</span>
          <span className="muted slot-modal-slot">slot {player.slot}</span>
          {player.goal_completed && <span className="badge badge-done">Goal!</span>}
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <div className="slot-modal-meta">
        <span className="slot-modal-status">
          {player.checks_done} / {player.checks_total} checks · {player.completion_pct}% · {player.status_label}
        </span>
        {detail?.submitter_username && (
          <span className={`slot-modal-attribution${isYourSlot ? " is-yours" : ""}`}>
            {isYourSlot
              ? "This is your slot"
              : <>Submitted by <strong>@{detail.submitter_username}</strong></>}
          </span>
        )}
      </div>

      <nav className="slot-modal-tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={`slot-modal-tab${tab === key ? " is-active" : ""}`}
            onClick={() => setTab(key)}
          >
            {label}
            {detail && key === "items" && ` (${detail.items_received.length})`}
            {detail && key === "locations" && ` (${detail.locations.filter((l) => l.checked).length}/${detail.locations.length})`}
            {detail && key === "hints" && ` (${detail.hints.length})`}
          </button>
        ))}
      </nav>

      <div className="slot-modal-body">
        {response === null && <p className="loading">Loading…</p>}
        {isError(response) && (
          <p className="error">Couldn't load slot data: <code>{response.error}</code></p>
        )}

        {detail && tab === "overview" && (
          <div className="slot-overview">
            <div className="slot-overview-row">
              <span className="muted">Game</span>
              <span>{player.game}</span>
            </div>
            <div className="slot-overview-row">
              <span className="muted">Status</span>
              <span>{player.status_label}</span>
            </div>
            <div className="slot-overview-row">
              <span className="muted">Checks</span>
              <span>{player.checks_done} / {player.checks_total} ({player.completion_pct}%)</span>
            </div>
            <div className="slot-overview-row">
              <span className="muted">Items received</span>
              <span>{detail.items_received.reduce((s, i) => s + i.amount, 0)} ({detail.items_received.length} unique)</span>
            </div>
            <div className="slot-overview-row">
              <span className="muted">Hints</span>
              <span>{detail.hints.length} total ({detail.hints.filter((h) => !h.found).length} open)</span>
            </div>
            <p className="muted slot-overview-note">
              Data scraped from archipelago.gg. Item, location, and hint
              names are taken straight from the per-slot tracker page.
            </p>
          </div>
        )}

        {detail && tab !== "overview" && (
          <div className="slot-modal-toolbar">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                tab === "items" ? "Search items…" :
                tab === "locations" ? "Search locations…" :
                "Search hints…"
              }
              aria-label={`Search ${tab}`}
              className="yaml-search slot-modal-search"
            />
            {tab === "locations" && (
              <label className="slot-modal-checkbox">
                <input
                  type="checkbox"
                  checked={showOnlyUnchecked}
                  onChange={(e) => setShowOnlyUnchecked(e.target.checked)}
                />
                Unchecked only
              </label>
            )}
            {tab === "hints" && (
              <label className="slot-modal-checkbox">
                <input
                  type="checkbox"
                  checked={showOnlyOpenHints}
                  onChange={(e) => setShowOnlyOpenHints(e.target.checked)}
                />
                Open hints only
              </label>
            )}
          </div>
        )}

        {detail && tab === "items" && (
          filteredItems.length === 0
            ? <p className="muted">{detail.items_received.length === 0 ? "No items received yet." : "No items match that search."}</p>
            : (
              <div className="table-wrapper">
                <table className="game-table slot-modal-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th className="center-column">Amount</th>
                      <th className="center-column">Last order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((it, idx) => (
                      <tr key={`${it.item}-${idx}`}>
                        <td>{it.item}</td>
                        <td className="center-column">{it.amount}</td>
                        <td className="center-column">{it.last_order || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
        )}

        {detail && tab === "locations" && (
          filteredLocations.length === 0
            ? <p className="muted">{detail.locations.length === 0 ? "No locations on this slot." : "No locations match."}</p>
            : (
              <div className="table-wrapper">
                <table className="game-table slot-modal-table">
                  <thead>
                    <tr>
                      <th>Location</th>
                      <th className="center-column">Checked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLocations.map((l, idx) => (
                      <tr key={`${l.location}-${idx}`}>
                        <td>{l.location}</td>
                        <td className="center-column">{l.checked ? "✔" : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
        )}

        {detail && tab === "hints" && (
          filteredHints.length === 0
            ? <p className="muted">{detail.hints.length === 0 ? "No hints involving this slot." : "No hints match."}</p>
            : (
              <div className="table-wrapper">
                <table className="game-table slot-modal-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Finder</th>
                      <th>Receiver</th>
                      <th>Location</th>
                      <th>Game</th>
                      <th className="center-column">Found</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredHints.map((h, idx) => (
                      <tr key={`${h.item}-${h.finder}-${idx}`} className={h.found ? "" : "slot-hint-open"}>
                        <td>{h.item}</td>
                        <td>{h.finder}</td>
                        <td>{h.receiver}</td>
                        <td>{h.location}{h.entrance ? ` (${h.entrance})` : ""}</td>
                        <td>{h.game}</td>
                        <td className="center-column">{h.found ? "✔" : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
        )}
      </div>

      <footer className="slot-modal-footer">
        <span className="muted slot-modal-source">
          {lastFetched && (
            <>data from archipelago.gg · fetched {lastFetched.toLocaleTimeString()}</>
          )}
        </span>
        <div className="slot-modal-actions">
          {detail?.tracker_url && (
            <a
              href={detail.tracker_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm"
            >
              View on archipelago.gg ↗
            </a>
          )}
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setRefreshTick((t) => t + 1)}
            disabled={response === null}
          >
            Refresh
          </button>
          <button type="button" className="btn btn-sm" onClick={onClose}>Close</button>
        </div>
      </footer>
    </dialog>
  );
}
