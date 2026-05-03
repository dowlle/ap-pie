/**
 * UX-09: shared sort + filter helpers for the LiveTracker player grid.
 * Mirrors the shape of yamlTable.ts but tuned for PlayerInfo: numeric sorts
 * for completion %/checks, an explicit ranking for status, and a per-key
 * default direction so the first click on each chip lands on the natural
 * reading order (highest % first, "most engaged" status first, A-Z for name
 * and game).
 */

import type { PlayerInfo } from "../api";

export type TrackerSortKey = "completion" | "status" | "name" | "game" | "checks";
export type TrackerSort = { key: TrackerSortKey; dir: "asc" | "desc" };

/** Lower rank = "more engaged". Used so asc-sort puts goal/playing first. */
const STATUS_RANK: Record<string, number> = {
  goal: 0,
  playing: 1,
  ready: 2,
  connected: 3,
  unknown: 4,
};

const trackerSortGetters: Record<TrackerSortKey, (p: PlayerInfo) => number | string> = {
  completion: (p) => p.completion_pct,
  checks: (p) => p.checks_done,
  status: (p) => STATUS_RANK[p.status_label] ?? 99,
  name: (p) => p.name.toLowerCase(),
  game: (p) => p.game.toLowerCase(),
};

/** First-click direction per key. Picked so the first toggle gives the user
 *  the obvious reading order: leaderboard-style for numeric, A-Z for text,
 *  goal-first for status. */
const FIRST_DIR: Record<TrackerSortKey, "asc" | "desc"> = {
  completion: "desc",
  checks: "desc",
  status: "asc",
  name: "asc",
  game: "asc",
};

/** Filter by case-insensitive substring across name + game, then sort.
 *  When sort is null, preserves the incoming order (which is whatever the
 *  backend returned - for archipelago.gg that's the table order from their
 *  HTML). */
export function filterAndSortPlayers(
  players: PlayerInfo[],
  search: string,
  sort: TrackerSort | null,
): PlayerInfo[] {
  const term = search.trim().toLowerCase();
  const filtered = term
    ? players.filter(
      (p) =>
        p.name.toLowerCase().includes(term) ||
        p.game.toLowerCase().includes(term),
    )
    : players;
  if (!sort) return filtered;
  const dir = sort.dir === "asc" ? 1 : -1;
  const get = trackerSortGetters[sort.key];
  return [...filtered].sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    if (av < bv) return -dir;
    if (av > bv) return dir;
    return a.slot - b.slot;
  });
}

/** 3-state toggle: off -> natural default -> opposite -> off.
 *  The "natural default" varies per key (see FIRST_DIR) so clicking
 *  Completion gives "highest %" first, but clicking Name gives A-Z first. */
export function nextTrackerSort(
  cur: TrackerSort | null,
  key: TrackerSortKey,
): TrackerSort | null {
  if (cur?.key !== key) return { key, dir: FIRST_DIR[key] };
  const opposite = cur.dir === "asc" ? "desc" : "asc";
  if (cur.dir === FIRST_DIR[key]) return { key, dir: opposite };
  return null;
}

/** Inline arrow indicator for the sort toggle chip. */
export function trackerSortIndicator(
  cur: TrackerSort | null,
  key: TrackerSortKey,
): string {
  if (cur?.key !== key) return " ↕";
  return cur.dir === "asc" ? " ↑" : " ↓";
}

/** ARIA-pressed value for the chip button (true when this key is the active sort). */
export function trackerSortPressed(
  cur: TrackerSort | null,
  key: TrackerSortKey,
): boolean {
  return cur?.key === key;
}
