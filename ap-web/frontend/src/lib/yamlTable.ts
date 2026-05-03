/**
 * Shared sort + filter helpers for YAML tables on RoomDetail (host) and
 * RoomPublic (player). Both pages list YAML rows with the same four
 * sortable columns so the implementation is centralised here.
 */

/**
 * Some YAML-generation tools name the output file with a Python `repr`
 * of the `game:` field, which for weighted-random pools is a dict like
 * `{'GameA': 10, 'GameB': 10}`. That lands in the table as visual noise
 * (`RiannehxRando - {'Manual_PokemonSS_Riannehx': 10, ...}.yaml`).
 *
 * When the filename contains a dict or list repr (detected by `{'` /
 * `{"` / `['` / `["`), collapse it to just `<playerName>.yaml`. The
 * game-list info is already in the Game column (often as the
 * "Random (N)" collapse from UX-12), so the filename column doesn't
 * need to repeat it. Real user-named files almost never contain those
 * sequences so the false-positive risk is tiny.
 */
export function cleanYamlFilename(
  filename: string,
  playerName: string,
  _game: string,
): string {
  if (/[{[]['"]/.test(filename)) {
    return `${playerName}.yaml`;
  }
  return filename;
}

export type YamlSortKey = "player" | "game" | "file" | "status" | "submitter";
export type YamlSort = { key: YamlSortKey; dir: "asc" | "desc" };

/** Minimal shape the helpers need. Both RoomYaml and PublicRoomYaml satisfy it.
 *  submitter_username is optional: only set on host-side reads, undefined on
 *  the public read. */
export interface YamlRow {
  id: number;
  player_name: string;
  game: string;
  filename: string;
  validation_status: string;
  submitter_username?: string | null;
}

const yamlSortGetters: Record<YamlSortKey, (y: YamlRow) => string> = {
  player: (y) => y.player_name.toLowerCase(),
  game: (y) => y.game.toLowerCase(),
  file: (y) => (y.filename ?? "").toLowerCase(),
  status: (y) => y.validation_status,
  submitter: (y) => (y.submitter_username ?? "").toLowerCase(),
};

/** Filter by case-insensitive substring across player/game/filename, then sort. */
export function filterAndSortYamls<T extends YamlRow>(
  yamls: T[],
  search: string,
  sort: YamlSort | null,
): T[] {
  const term = search.trim().toLowerCase();
  const filtered = term
    ? yamls.filter(
      (y) =>
        y.player_name.toLowerCase().includes(term) ||
        y.game.toLowerCase().includes(term) ||
        (y.filename ?? "").toLowerCase().includes(term),
    )
    : yamls;
  if (!sort) return filtered;
  const dir = sort.dir === "asc" ? 1 : -1;
  const get = yamlSortGetters[sort.key];
  return [...filtered].sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    if (av < bv) return -dir;
    if (av > bv) return dir;
    return a.id - b.id;
  });
}

/** 3-state toggle: off -> asc -> desc -> off. */
export function nextSort(cur: YamlSort | null, key: YamlSortKey): YamlSort | null {
  if (cur?.key !== key) return { key, dir: "asc" };
  if (cur.dir === "asc") return { key, dir: "desc" };
  return null;
}

/** Inline arrow indicator for the sort toggle button. */
export function sortIndicator(cur: YamlSort | null, key: YamlSortKey): string {
  if (cur?.key !== key) return " ↕";
  return cur.dir === "asc" ? " ↑" : " ↓";
}

/** ARIA-sort attribute value for the th element. */
export function ariaSortValue(
  cur: YamlSort | null,
  key: YamlSortKey,
): "ascending" | "descending" | "none" {
  if (cur?.key !== key) return "none";
  return cur.dir === "asc" ? "ascending" : "descending";
}
