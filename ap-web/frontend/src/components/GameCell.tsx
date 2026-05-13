import { useState } from "react";
import type { APWorldInfo, FuzzResult } from "../api";
import FuzzResultPill from "./FuzzResultPill";

/**
 * Renders a YAML's `game:` field for the room tables (host + public).
 *
 * UX-12 + UX-16:
 *   - Single-game YAMLs: link to the matching APWorld card on /apworlds
 *     when the game is in the index, or plain text otherwise.
 *   - Multi-game YAMLs (BUG-03 join: "Game A / Game B / Game C" from
 *     `extract_player_info` for weighted-dict + uniform-list random
 *     pools): collapse to "Random (N)" with a click-to-expand list.
 *
 * FEAT-28 v2 follow-up (replaces the standalone Version column): each
 * game name gets a tiny version pill rendered inline:
 *   - "v1.2.0" neutral when YAML's declared version matches the room pin
 *   - "v1.2.0" orange when YAML declares a version different from the pin
 *   - "Core" italic for built-in / core-AP games (no pin needed)
 *   - no pill at all when the YAML doesn't declare a version and the
 *     game isn't built-in
 *
 * `apworldVersions` is the YAML row's cached `requires.game` map (may
 * be null/empty). `pinByApworld` is the room's pin map (apworld_name ->
 * version). Both passed in so the host + public tables can share one
 * cell rendering without duplicating the join logic.
 */
const SEPARATOR = " / ";

export default function GameCell({
  game,
  lookup,
  apworldVersions,
  pinByApworld,
}: {
  game: string;
  lookup: Map<string, APWorldInfo> | null;
  apworldVersions?: Record<string, string> | null;
  pinByApworld?: Map<string, string>;
}) {
  const games = game
    .split(SEPARATOR)
    .map((s) => s.trim())
    .filter(Boolean);

  if (games.length <= 1) {
    return (
      <SingleGameRow
        game={games[0] ?? game}
        lookup={lookup}
        apworldVersions={apworldVersions}
        pinByApworld={pinByApworld}
      />
    );
  }
  return (
    <MultiGameCell
      games={games}
      lookup={lookup}
      apworldVersions={apworldVersions}
      pinByApworld={pinByApworld}
    />
  );
}

function VersionPill({
  game,
  lookup,
  apworldVersions,
  pinByApworld,
}: {
  game: string;
  lookup: Map<string, APWorldInfo> | null;
  apworldVersions?: Record<string, string> | null;
  pinByApworld?: Map<string, string>;
}) {
  const world = lookup?.get(game);
  // Game not in the index at all - render a warning badge so the host
  // knows they may need to chase the player for the .apworld file.
  // Could be a custom/community APWorld not yet contributed to the
  // dowlle index, OR a built-in AP game whose stub TOML hasn't been
  // added (e.g. VVVVVV). Either way the host can't auto-pin it; the
  // tooltip explains the ambiguity.
  //
  // While the lookup is still loading (lookup === null) we render
  // nothing rather than a false-positive Missing flash.
  if (!world) {
    if (!lookup) return null;
    return (
      <span
        className="game-pill game-pill-missing"
        title={`${game}: not in the dowlle/Archipelago-index. Could be a community APWorld or a built-in AP game without a stub - if the player isn't on AP core, contact them for the .apworld file.`}
      >
        ⚠ Missing
      </span>
    );
  }

  // In the index but ships with AP core (no downloadable APWorld) -
  // render the muted "Core" italic pill. No version is meaningful here
  // because the player gets it from their AP install.
  if (world.is_builtin) {
    return (
      <span
        className="game-pill game-pill-core"
        title={`${game}: ships with Archipelago core - no APWorld pin needed`}
      >
        Core
      </span>
    );
  }

  // Otherwise the game is a community APWorld in the index. Three
  // sub-cases:
  //   1. YAML declares a version AND it differs from the room's pin
  //      -> orange warn pill (the player's YAML may need upgrading,
  //      or the host may want to bump the pin).
  //   2. YAML declares a version that matches (or no pin exists yet)
  //      -> neutral pill with the YAML's declared version.
  //   3. YAML doesn't declare a version, but the room has a pin
  //      -> neutral pill with the room's pinned version (so the host
  //      sees what's currently set, common after auto-pin).
  //   4. Neither YAML version nor room pin -> nothing (rare; happens
  //      when auto-pin is off and the host hasn't pinned yet).
  const declared = apworldVersions?.[game];
  const apworldName = world.name;
  const pinned = pinByApworld?.get(apworldName);

  if (declared) {
    const warn = pinned !== undefined && declared !== pinned;
    const titleText = warn
      ? `${game}: YAML wants v${declared}, room is pinned to v${pinned}`
      : `${game}: v${declared}`;
    return (
      <span
        className={warn ? "game-pill game-pill-warn" : "game-pill"}
        title={titleText}
      >
        v{declared}
      </span>
    );
  }
  if (pinned) {
    return (
      <span
        className="game-pill"
        title={`${game}: room is pinned to v${pinned} (YAML doesn't declare a version)`}
      >
        v{pinned}
      </span>
    );
  }
  return null;
}

/**
 * FEAT-35: pick the effective fuzz_result for this YAML row.
 *
 * The "effective" version is whichever version's verdict applies to the
 * row as rendered:
 *   1. YAML's declared version, when present in the index
 *   2. Otherwise the room's pin for this game's apworld
 *
 * Returns null when the game has no APWorld match in the lookup, when the
 * matched APWorld is built-in (no fuzz data on AP core games), when
 * neither declared nor pinned is set, or when the resolved version
 * carries no fuzz_result.
 */
function effectiveFuzzResult(
  game: string,
  lookup: Map<string, APWorldInfo> | null,
  apworldVersions: Record<string, string> | null | undefined,
  pinByApworld: Map<string, string> | undefined,
): FuzzResult | null {
  if (!lookup) return null;
  const world = lookup.get(game);
  if (!world || world.is_builtin) return null;
  const declared = apworldVersions?.[game];
  const pinned = pinByApworld?.get(world.name);
  const ver = declared ?? pinned;
  if (!ver) return null;
  const match = world.versions.find((v) => v.version === ver);
  return match?.fuzz_result ?? null;
}

function GameLink({
  game,
  lookup,
}: {
  game: string;
  lookup: Map<string, APWorldInfo> | null;
}) {
  const world = lookup?.get(game);
  if (!world) return <>{game}</>;
  return (
    <a
      href={`/apworlds?search=${encodeURIComponent(game)}`}
      title={`Open ${world.display_name} on /apworlds`}
      className="game-link"
    >
      {game}
    </a>
  );
}

/**
 * FEAT-34: tiny inline icon links to the APWorld's setup guide and
 * tracker (when the index TOML has those fields populated). Players see
 * these next to the version pill in YAML rows — the "APWorlds you need
 * to install" panel was removed 2026-05-03 in favour of inline pills,
 * so this is the player-facing home for those URLs.
 *
 * Stroke-based SVG icons (Feather-style) so they inherit `currentColor`
 * and scale with the parent font-size; gives a much cleaner read than
 * emoji at small sizes.
 *
 * Render nothing when neither field is set, so cells stay tight for
 * the common case.
 */
function SetupGuideIcon() {
  // Open book outline.
  return (
    <svg
      className="game-aux-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z" />
      <path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z" />
    </svg>
  );
}

function TrackerIcon() {
  // Concentric crosshair — reads as "live tracker / target" cleanly at
  // 1em.
  return (
    <svg
      className="game-aux-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  );
}

function GameAuxLinks({
  game,
  lookup,
}: {
  game: string;
  lookup: Map<string, APWorldInfo> | null;
}) {
  const world = lookup?.get(game);
  if (!world) return null;
  if (!world.setup_guide && !world.tracker) return null;
  return (
    <span className="game-aux-links">
      {world.setup_guide && (
        <a
          href={world.setup_guide}
          target="_blank"
          rel="noopener noreferrer"
          className="game-aux-link"
          title={`${game}: author's setup / install guide`}
          aria-label={`Setup guide for ${game}`}
        >
          <SetupGuideIcon />
        </a>
      )}
      {world.tracker && (
        <a
          href={world.tracker}
          target="_blank"
          rel="noopener noreferrer"
          className="game-aux-link"
          title={`${game}: live tracker / PopTracker pack`}
          aria-label={`Tracker for ${game}`}
        >
          <TrackerIcon />
        </a>
      )}
    </span>
  );
}

function SingleGameRow({
  game,
  lookup,
  apworldVersions,
  pinByApworld,
}: {
  game: string;
  lookup: Map<string, APWorldInfo> | null;
  apworldVersions?: Record<string, string> | null;
  pinByApworld?: Map<string, string>;
}) {
  const fuzz = effectiveFuzzResult(game, lookup, apworldVersions, pinByApworld);
  return (
    <span className="game-cell-inline">
      <GameLink game={game} lookup={lookup} />
      <VersionPill
        game={game}
        lookup={lookup}
        apworldVersions={apworldVersions}
        pinByApworld={pinByApworld}
      />
      {/* FEAT-35: compact fuzz verdict pill next to the version. Renders
          nothing for clean-or-absent core games; flaky/broken surface as
          coloured pills with a worst_hook tooltip. */}
      <FuzzResultPill fuzz_result={fuzz} />
      <GameAuxLinks game={game} lookup={lookup} />
    </span>
  );
}

function MultiGameCell({
  games,
  lookup,
  apworldVersions,
  pinByApworld,
}: {
  games: string[];
  lookup: Map<string, APWorldInfo> | null;
  apworldVersions?: Record<string, string> | null;
  pinByApworld?: Map<string, string>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span className="multi-game-cell">
      <button
        type="button"
        className="multi-game-toggle"
        aria-expanded={open}
        title={games.join(", ")}
        onClick={() => setOpen((v) => !v)}
      >
        Random ({games.length})
        <span className="multi-game-caret" aria-hidden="true">
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <ul className="multi-game-list">
          {games.map((g, i) => {
            const fuzz = effectiveFuzzResult(g, lookup, apworldVersions, pinByApworld);
            return (
              <li key={`${g}-${i}`}>
                <span className="game-cell-inline">
                  <GameLink game={g} lookup={lookup} />
                  <VersionPill
                    game={g}
                    lookup={lookup}
                    apworldVersions={apworldVersions}
                    pinByApworld={pinByApworld}
                  />
                  <FuzzResultPill fuzz_result={fuzz} />
                  <GameAuxLinks game={g} lookup={lookup} />
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </span>
  );
}
