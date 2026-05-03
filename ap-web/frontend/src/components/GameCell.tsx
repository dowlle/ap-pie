import { useState } from "react";
import type { APWorldInfo } from "../api";

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
  return (
    <span className="game-cell-inline">
      <GameLink game={game} lookup={lookup} />
      <VersionPill
        game={game}
        lookup={lookup}
        apworldVersions={apworldVersions}
        pinByApworld={pinByApworld}
      />
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
          {games.map((g, i) => (
            <li key={`${g}-${i}`}>
              <span className="game-cell-inline">
                <GameLink game={g} lookup={lookup} />
                <VersionPill
                  game={g}
                  lookup={lookup}
                  apworldVersions={apworldVersions}
                  pinByApworld={pinByApworld}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}
