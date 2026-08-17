import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getAPWorlds,
  getApworldBuilderSchema,
  getInstalledAPWorlds,
  getRooms,
  installAPWorld,
  removeAPWorld,
  refreshAPWorldIndex,
  submitYamlContentToRoom,
  type APWorldInfo,
  type APWorldVersion,
  type BuilderSchemaEntry,
  type InstalledAPWorld,
  type Room,
} from "../api";
import { useFeature } from "../context/FeaturesContext";
import { useAuth } from "../context/AuthContext";
import CreateRoomModal from "../components/CreateRoomModal";
import FuzzResultPill from "../components/FuzzResultPill";
import YamlBuilder from "../components/YamlBuilder";

/**
 * /apworlds - browser for the Archipelago-index (now sourced from
 * dowlle/Archipelago-index). FEAT-21 redesign:
 *
 *   - One card per APWorld (was: one row in a wide table with a single
 *     version dropdown). Cards stack all available versions so the host
 *     can see the full version history at a glance.
 *   - Each version row shows source (URL / local-in-index / built-in),
 *     sha256 fingerprint when present (truncated to 7 chars), and a
 *     direct "Download" link to the index proxy that works for both
 *     URL- and local-backed entries.
 *   - Install / Remove buttons stay (gated on the `generation` feature
 *     flag - they only matter when this server runs AP itself; the
 *     production ap-pie.com surface uses the proxy download for players
 *     to install locally instead).
 */

const VERSIONS_COLLAPSED_LIMIT = 3;

function isDiscordUrl(url: string): boolean {
  return /^https?:\/\/(www\.)?(discord\.com|discord\.gg|discordapp\.com)\//i.test(url);
}

function isGitHubUrl(url: string): boolean {
  return /^https?:\/\/(www\.)?github\.com\//i.test(url);
}

function isArchipelagoUrl(url: string): boolean {
  return /^https?:\/\/(www\.)?archipelago\.gg(\/|$)/i.test(url);
}

/** Derive the canonical `https://github.com/<owner>/<repo>` URL from any
 * version's download URL when the index points at GitHub releases OR
 * a raw blob (raw.githubusercontent.com/<owner>/<repo>/<sha>/...). Some
 * TOMLs (e.g. manual_umamusumeprettyderby_quindo) point at raw blobs
 * instead of release assets — same canonical repo, different host.
 * Returns null if no version has a parseable GitHub-family URL. */
function deriveGitHubRepoUrl(versions: APWorldVersion[]): string | null {
  for (const v of versions) {
    if (!v.url) continue;
    const m = v.url.match(
      /^https?:\/\/(?:github\.com|raw\.githubusercontent\.com)\/([^/]+)\/([^/]+)\//i,
    );
    if (m) return `https://github.com/${m[1]}/${m[2]}`;
  }
  return null;
}

function DiscordIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className="apworld-card-icon-svg"
    >
      <path d="M19.27 5.33C17.94 4.71 16.5 4.26 15 4a.09.09 0 0 0-.07.03c-.18.33-.39.76-.53 1.09a16.09 16.09 0 0 0-4.8 0c-.14-.34-.35-.76-.54-1.09a.1.1 0 0 0-.07-.03C7.5 4.26 6.05 4.71 4.72 5.33a.07.07 0 0 0-.03.03C2.04 9.46 1.32 13.5 1.68 17.48a.08.08 0 0 0 .03.06c1.8 1.33 3.55 2.13 5.26 2.64a.08.08 0 0 0 .08-.04c.4-.55.76-1.13 1.07-1.74a.08.08 0 0 0-.04-.11c-.57-.22-1.12-.49-1.65-.79a.08.08 0 0 1-.01-.13l.33-.26a.08.08 0 0 1 .08-.01c3.46 1.58 7.21 1.58 10.63 0a.08.08 0 0 1 .09.01l.33.26a.08.08 0 0 1-.01.13c-.53.31-1.08.57-1.65.79a.08.08 0 0 0-.04.11c.32.61.68 1.19 1.07 1.74a.08.08 0 0 0 .08.04c1.72-.51 3.46-1.31 5.27-2.64a.08.08 0 0 0 .03-.06c.43-4.6-.72-8.6-3.07-12.12a.06.06 0 0 0-.03-.03ZM8.52 15.06c-1.03 0-1.88-.95-1.88-2.11s.83-2.11 1.88-2.11c1.05 0 1.89.96 1.88 2.11 0 1.16-.84 2.11-1.88 2.11Zm6.97 0c-1.03 0-1.88-.95-1.88-2.11s.83-2.11 1.88-2.11c1.05 0 1.89.96 1.88 2.11 0 1.16-.83 2.11-1.88 2.11Z" />
    </svg>
  );
}

function GitHubIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className="apworld-card-icon-svg"
    >
      <path d="M12 2C6.48 2 2 6.58 2 12.26c0 4.5 2.87 8.32 6.84 9.67.5.1.68-.22.68-.49 0-.24-.01-.87-.01-1.71-2.78.62-3.37-1.37-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.63.07-.62.07-.62 1 .07 1.53 1.05 1.53 1.05.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.07 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.27 2.75 1.05A9.4 9.4 0 0 1 12 7.07c.85.01 1.71.12 2.51.34 1.91-1.33 2.75-1.05 2.75-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.64 1.03 2.75 0 3.94-2.34 4.81-4.57 5.06.36.32.68.93.68 1.88 0 1.36-.01 2.46-.01 2.79 0 .27.18.59.69.49A10.05 10.05 0 0 0 22 12.26C22 6.58 17.52 2 12 2Z" />
    </svg>
  );
}

/** The actual archipelago.gg favicon (a teal "three people" mark),
 * served from `public/archipelago-favicon.png` so we don't have to
 * redraw the brand. CSS applies a greyscale filter + reduced opacity
 * at rest and lifts brightness/opacity on hover/focus to match the
 * muted → accent-light tone shift the SVG icons get via currentColor. */
function ArchipelagoIcon() {
  return (
    <img
      src="/archipelago-favicon.png"
      alt=""
      aria-hidden="true"
      className="apworld-card-icon-img"
    />
  );
}

/** Generic globe — used when `home` is set but not a host we have a
 * brand glyph for (itch pages, dev blogs, self-hosted Gitea / GitLab,
 * etc.). Reads as "some external homepage" without committing to a
 * specific brand. */
function GlobeIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="apworld-card-icon-svg"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18Z" />
    </svg>
  );
}

function SetupGuideIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="apworld-card-icon-svg"
    >
      <path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z" />
      <path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z" />
    </svg>
  );
}

function TrackerIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="apworld-card-icon-svg"
    >
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
    </svg>
  );
}

function compareVersions(a: string, b: string): number {
  const partsA = a.split(/[.\-]/).map((p) => (/^\d+$/.test(p) ? parseInt(p, 10) : p));
  const partsB = b.split(/[.\-]/).map((p) => (/^\d+$/.test(p) ? parseInt(p, 10) : p));
  const len = Math.max(partsA.length, partsB.length);
  for (let i = 0; i < len; i++) {
    const pa = partsA[i] ?? 0;
    const pb = partsB[i] ?? 0;
    if (typeof pa === "number" && typeof pb === "number") {
      if (pa !== pb) return pa - pb;
    } else {
      const sa = String(pa), sb = String(pb);
      if (sa !== sb) return sa < sb ? -1 : 1;
    }
  }
  return 0;
}

function shortSha(sha: string | null): string {
  if (!sha) return "";
  return sha.slice(0, 7);
}

/**
 * Documented meanings for tags that ship in the dowlle/Archipelago-index
 * TOMLs. Unknown tags render with no tooltip (the raw label is good
 * enough for hand-curated tags). Add entries here as we learn what each
 * tag means.
 *
 * BUG-04 / UX-14: "ad" is "after-dark / adult content" - confirmed from
 * the apworlds_for_room docstring in api/apworlds.py and AP community
 * usage. Surface it as a hover tooltip so hosts know what they're
 * pinning.
 */
const TAG_DESCRIPTIONS: Record<string, string> = {
  ad: "After-dark / adult-content APWorld",
};

/**
 * FEAT-34: stability comes from the OPS-16 sheet backfill. We render
 * known values as a coloured chip; anything else (or absence) renders
 * nothing — silent absence is the correct default per the design note.
 */
function StabilityChip({ stability }: { stability: string | null }) {
  if (!stability) return null;
  const known = ["stable", "unstable", "alpha", "beta"];
  const value = stability.toLowerCase();
  if (!known.includes(value)) return null;
  const titleMap: Record<string, string> = {
    stable: "Marked stable by the APWorld author",
    unstable: "Marked unstable — expect occasional issues",
    alpha: "Marked alpha — early development, expect bugs",
    beta: "Marked beta — feature-complete but still hardening",
  };
  return (
    <span
      className={`apworld-stability apworld-stability-${value}`}
      title={titleMap[value]}
    >
      {value}
    </span>
  );
}

function VersionRow({
  world,
  v,
  installed,
  installing,
  generationOn,
  onInstall,
  onBuild,
  building,
}: {
  world: APWorldInfo;
  v: APWorldVersion;
  installed: InstalledAPWorld | undefined;
  installing: boolean;
  generationOn: boolean;
  onInstall: (name: string, version: string) => void;
  /** FEAT-38: open the guided YAML builder for this exact version. */
  onBuild: (name: string, version: string) => void;
  building: boolean;
}) {
  const downloadHref = `/api/apworlds/${world.name}/${encodeURIComponent(v.version)}/download`;
  const isCurrent = installed?.version === v.version;
  const sourceLabel = v.source === "url"
    ? "URL"
    : v.source === "local"
    ? "in-index"
    : "built-in";

  return (
    <li className="apworld-version-row">
      <span className="apworld-version-label">
        <span className="apworld-version-num">v{v.version}</span>
        <span className="apworld-version-source" title={`Source: ${sourceLabel}`}>{sourceLabel}</span>
        {v.sha256 && (
          <span className="apworld-version-sha" title={`sha256: ${v.sha256}`}>
            {shortSha(v.sha256)}
          </span>
        )}
        {/* FEAT-35: per-version fuzz verdict. Null fuzz_result renders
            nothing; clean is a tiny green dot; flaky/broken are coloured
            pills with worst_hook tooltip. */}
        <FuzzResultPill fuzz_result={v.fuzz_result} version={v.version} />
        {isCurrent && <span className="badge badge-done apworld-version-current">installed</span>}
      </span>
      <span className="apworld-version-actions">
        {(v.source === "url" || v.source === "local") && (
          <button
            className="btn btn-sm"
            onClick={() => onBuild(world.name, v.version)}
            disabled={building}
            title={`Build a ${world.display_name} YAML for this version with the guided form`}
          >
            {building ? "Loading…" : "Create YAML"}
          </button>
        )}
        {(v.source === "url" || v.source === "local") && (
          <a className="btn btn-sm" href={downloadHref} download>Download</a>
        )}
        {generationOn && (v.source === "url" || v.source === "local") && !isCurrent && (
          <button
            className="btn btn-sm btn-primary"
            onClick={() => onInstall(world.name, v.version)}
            disabled={installing}
          >
            {installing ? "..." : "Install"}
          </button>
        )}
      </span>
    </li>
  );
}

/**
 * Render the apworld card's external-links area. Three pieces:
 *
 *  1. Text URL row — only when `home` is set AND not one of the
 *     icon-recognised hosts (Discord / GitHub / Archipelago.gg).
 *     Otherwise we'd be showing the same URL twice (text + icon).
 *  2. Icon row — home glyph (when recognised) + a derived GitHub icon
 *     when home didn't already provide one and the index download URL
 *     points at a GitHub release + setup guide + tracker icons.
 *
 * The derived GitHub link is the user's verification path: if `home`
 * isn't a repo, we point at the repo we actually pulled the .apworld
 * from. Cards where neither `home` nor any version URL is GitHub end
 * up with no GitHub icon — that's an index data gap worth chasing
 * (the TOML didn't carry a verifiable source).
 */
function HomeAndIconRow({ world }: { world: APWorldInfo }) {
  let homeIcon:
    | { node: ReactElement; href: string; title: string; label: string; kind: "discord" | "github" | "archipelago" | "other" }
    | null = null;
  if (world.home) {
    if (isDiscordUrl(world.home)) {
      homeIcon = {
        node: <DiscordIcon />,
        href: world.home,
        title: `Discord: ${world.home}`,
        label: "Open Discord channel",
        kind: "discord",
      };
    } else if (isGitHubUrl(world.home)) {
      homeIcon = {
        node: <GitHubIcon />,
        href: world.home,
        title: `GitHub: ${world.home}`,
        label: "Open GitHub repository",
        kind: "github",
      };
    } else if (isArchipelagoUrl(world.home)) {
      homeIcon = {
        node: <ArchipelagoIcon />,
        href: world.home,
        title: `Archipelago.gg: ${world.home}`,
        label: "Open Archipelago.gg page",
        kind: "archipelago",
      };
    } else {
      homeIcon = {
        node: <GlobeIcon />,
        href: world.home,
        title: `Project page: ${world.home}`,
        label: "Open project homepage",
        kind: "other",
      };
    }
  }

  // Derive a GitHub repo from version URLs when we don't already have
  // a GitHub icon from `home`. This is the trust anchor — it points at
  // wherever the index actually pulls the .apworld from.
  const derivedRepo =
    homeIcon?.kind === "github" ? null : deriveGitHubRepoUrl(world.versions);

  const hasIcons = Boolean(homeIcon) || Boolean(derivedRepo) || Boolean(world.setup_guide) || Boolean(world.tracker);

  return (
    <>
      {hasIcons && (
        <div className="apworld-card-icons">
          {homeIcon && (
            <a
              href={homeIcon.href}
              target="_blank"
              rel="noreferrer"
              className="apworld-card-icon"
              title={homeIcon.title}
              aria-label={homeIcon.label}
            >
              {homeIcon.node}
            </a>
          )}
          {derivedRepo && (
            <a
              href={derivedRepo}
              target="_blank"
              rel="noreferrer"
              className="apworld-card-icon"
              title={`Source repo (from download URL): ${derivedRepo}`}
              aria-label="Open source GitHub repository"
            >
              <GitHubIcon />
            </a>
          )}
          {world.setup_guide && (
            <a
              href={world.setup_guide}
              target="_blank"
              rel="noopener noreferrer"
              className="apworld-card-icon"
              title={`Setup guide: ${world.setup_guide}`}
              aria-label="Open setup guide"
            >
              <SetupGuideIcon />
            </a>
          )}
          {world.tracker && (
            <a
              href={world.tracker}
              target="_blank"
              rel="noopener noreferrer"
              className="apworld-card-icon"
              title={`Live tracker / PopTracker pack: ${world.tracker}`}
              aria-label="Open tracker"
            >
              <TrackerIcon />
            </a>
          )}
        </div>
      )}
    </>
  );
}

function WorldCard({
  world,
  installed,
  installingVersion,
  generationOn,
  onInstall,
  onRemove,
  onBuild,
  buildingVersion,
}: {
  world: APWorldInfo;
  installed: InstalledAPWorld | undefined;
  installingVersion: string | null;
  generationOn: boolean;
  onInstall: (name: string, version: string) => void;
  onRemove: (name: string) => void;
  onBuild: (name: string, version: string) => void;
  buildingVersion: string | null;
}) {
  // Always show all versions sorted descending (latest first). If the index
  // only contained one version and that's the latest, the list is just one
  // row - still cleaner than the old single-dropdown row layout.
  const versions = useMemo(
    () => [...world.versions].sort((a, b) => compareVersions(b.version, a.version)),
    [world.versions],
  );
  const downloadable = versions.filter((v) => v.source === "url" || v.source === "local");
  const builtinOnly = downloadable.length === 0;
  const [showAllVersions, setShowAllVersions] = useState(false);
  const hasMoreVersions = versions.length > VERSIONS_COLLAPSED_LIMIT;
  const visibleVersions =
    showAllVersions || !hasMoreVersions
      ? versions
      : versions.slice(0, VERSIONS_COLLAPSED_LIMIT);

  return (
    <article className="apworld-card">
      <header className="apworld-card-head">
        <div className="apworld-card-title">
          <h3>{world.display_name}</h3>
          <code className="apworld-card-key">{world.name}</code>
        </div>
        <div className="apworld-card-badges">
          {world.disabled && <span className="badge badge-stopped">Disabled</span>}
          {world.is_builtin && <span className="badge badge-builtin">Built-in</span>}
          {!world.is_builtin && !world.disabled && (
            <span className="badge badge-save">Community</span>
          )}
          <StabilityChip stability={world.stability} />
          {world.tags.map((t) => (
            <span key={t} className="tag" title={TAG_DESCRIPTIONS[t]}>{t}</span>
          ))}
        </div>
      </header>

      <HomeAndIconRow world={world} />


      {builtinOnly ? (
        <p className="apworld-card-note muted">
          {world.is_builtin
            ? "No external versions in the index - this APWorld ships with Archipelago itself."
            : "No versions of this APWorld have passed the security audit or fuzzer at the moment."}
        </p>
      ) : (
        <>
          <ul className="apworld-version-list">
            {visibleVersions.map((v) => (
              <VersionRow
                key={v.version}
                world={world}
                v={v}
                installed={installed}
                installing={installingVersion === v.version}
                generationOn={generationOn}
                onInstall={onInstall}
                onBuild={onBuild}
                building={buildingVersion === v.version}
              />
            ))}
          </ul>
          {hasMoreVersions && (
            <button
              type="button"
              className="apworld-version-toggle"
              onClick={() => setShowAllVersions((s) => !s)}
            >
              {showAllVersions
                ? "Show fewer versions"
                : `Show ${versions.length - VERSIONS_COLLAPSED_LIMIT} more version${
                    versions.length - VERSIONS_COLLAPSED_LIMIT === 1 ? "" : "s"
                  }`}
            </button>
          )}
        </>
      )}

      {generationOn && installed && (
        <div className="apworld-card-foot">
          <span className="muted">Currently installed: v{installed.version ?? "?"}</span>
          <button className="btn btn-sm btn-danger" onClick={() => onRemove(world.name)}>
            Remove install
          </button>
        </div>
      )}
    </article>
  );
}

/**
 * FEAT-38 (§2.5a): review-step room actions for the index "Create YAML"
 * flow. The built YAML can be attached to one of the user's own open rooms
 * (via the same public submit endpoint players use) or carried into a
 * fresh room via CreateRoomModal.
 */
function RoomAttach({
  yamlContent,
  onCreateRoom,
}: {
  yamlContent: string;
  onCreateRoom: (yamlContent: string) => void;
}) {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState<{ roomId: string; msg: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getRooms("open")
      .then((r) => { if (!cancelled) setRooms(r); })
      .catch(() => { /* room list unavailable - create-room path still works */ });
    return () => { cancelled = true; };
  }, []);

  const handleAdd = async () => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const r = await submitYamlContentToRoom(selected, yamlContent);
      setAdded({
        roomId: selected,
        msg: `Added ${r.player_name} (${r.game}) - ${r.validation_status}`,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add YAML to the room");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="settings-section">
      <h3>Use this YAML</h3>
      {added ? (
        <p className="settings-aux-note" style={{ margin: 0, color: "var(--green)" }}>
          ✓ {added.msg}. <Link to={`/rooms/${added.roomId}`}>Open the room</Link>
        </p>
      ) : (
        <>
          <div className="settings-controls">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              style={{ flex: 1, minWidth: "12rem" }}
            >
              <option value="">
                {rooms.length ? "Select one of your open rooms…" : "No open rooms"}
              </option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={handleAdd}
              disabled={!selected || busy}
            >
              {busy ? "Adding…" : "Add to room"}
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => onCreateRoom(yamlContent)}
              disabled={busy}
            >
              Create room with this YAML
            </button>
          </div>
          <p className="settings-hint">
            Adding goes through the room's normal submission flow, so its
            claim/login rules still apply. Or just download the file and use
            it anywhere.
          </p>
          {error && <p className="settings-error" style={{ margin: 0 }}>{error}</p>}
        </>
      )}
    </section>
  );
}

export default function APWorlds() {
  const generationOn = useFeature("generation");
  // Refresh button is admin-only (matches the @requires_admin gate on
  // POST /api/apworlds/refresh added 2026-05-03 - approved non-admin
  // hosts can browse the index and pin per-room versions, but the
  // global "pull from upstream" action stays with admins).
  const { user } = useAuth();
  const isAdmin = !!user?.is_admin;
  const [available, setAvailable] = useState<APWorldInfo[]>([]);
  const [installed, setInstalled] = useState<InstalledAPWorld[]>([]);
  // UX-16 hand-off: GameCell links from RoomDetail/RoomPublic land at
  // /apworlds?search=<game>. Prefill the search box from the URL on
  // mount so the card list filters down to the matching world.
  const [search, setSearch] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("search") ?? "";
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // installing key = `${name}@${version}` so multiple cards can show their
  // own per-version spinner without clobbering each other.
  const [installing, setInstalling] = useState<string | null>(null);
  const [error, setError] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  // FEAT-38: the index "Create YAML" flow. `builder` holds the fetched
  // schema entry while the builder modal is open; `building` is the
  // name@version whose schema fetch is in flight (per-row spinner);
  // `pendingYaml` carries the built YAML into the create-room flow.
  const navigate = useNavigate();
  // UX-20: client-side sort + filter over the card grid. The index is ~600
  // entries and the whole list is already in memory, so this never needs the
  // server. Search stays server-side (?search=) as before.
  const [sortBy, setSortBy] = useState<"name" | "name-desc" | "stability">("name");
  const [stabilityFilter, setStabilityFilter] = useState("");
  const [installableOnly, setInstallableOnly] = useState(false);

  const [builder, setBuilder] = useState<BuilderSchemaEntry | null>(null);
  const [building, setBuilding] = useState<string | null>(null);
  const [createRoomOpen, setCreateRoomOpen] = useState(false);
  const [pendingYaml, setPendingYaml] = useState<string | null>(null);

  const handleBuild = async (name: string, version: string) => {
    setBuilding(`${name}@${version}`);
    setError("");
    try {
      const entry = await getApworldBuilderSchema(name, version);
      if (entry.pending) {
        setError(`Still deriving the option form for ${entry.display_name} v${version} - try again in a few seconds.`);
      } else if (!entry.schema) {
        // Only when the archive itself could not be understood. A world with
        // no options of its own still gets a builder: Archipelago's own
        // options apply to every game, and name / game / requires alone is a
        // valid YAML.
        setError(`The option form for ${entry.display_name} v${version} could not be read from the apworld - grab the template from the game's setup guide instead.`);
      } else {
        setBuilder(entry);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load the builder");
    } finally {
      setBuilding(null);
    }
  };

  const handleRoomCreated = async (room: Room) => {
    setCreateRoomOpen(false);
    const yaml = pendingYaml;
    setPendingYaml(null);
    setBuilder(null);
    if (yaml) {
      try {
        await submitYamlContentToRoom(room.id, yaml);
      } catch (e) {
        // The room exists either way - land the user on it and surface why
        // the YAML didn't attach so they can paste/upload it there.
        window.alert(
          `Room created, but the YAML couldn't be added automatically: ` +
          `${e instanceof Error ? e.message : "submission failed"}. ` +
          `You can paste it on the room page.`,
        );
      }
    }
    navigate(`/rooms/${room.id}`);
  };

  const installedMap = useMemo(
    () => new Map(installed.map((w) => [w.name, w])),
    [installed],
  );

  // Stability values present in the current result set, so the filter never
  // offers a value that would return nothing. `null` (most of the index
  // after OPS-16 backfilled ~214 of 616) is offered as "not recorded".
  const stabilityValues = useMemo(() => {
    const seen = new Set<string>();
    for (const w of available) if (w.stability) seen.add(w.stability);
    return [...seen].sort();
  }, [available]);

  const visible = useMemo(() => {
    let list = available;
    if (stabilityFilter === "__unset__") {
      list = list.filter((w) => !w.stability);
    } else if (stabilityFilter) {
      list = list.filter((w) => w.stability === stabilityFilter);
    }
    if (installableOnly) {
      list = list.filter((w) => w.downloadable_versions.length > 0);
    }
    // Order the index by what people actually read. The API returns TOML
    // filename order (`sorted(toml_dir.iterdir())` in parse_index_dir), which
    // is why "Ape Escape 3" could land before "Against the Storm": the keys
    // are ape_escape_3 and against_the_storm. Sorting on display_name fixes
    // the surprise without changing the API.
    const byName = (a: APWorldInfo, b: APWorldInfo) =>
      (a.display_name || a.name).localeCompare(b.display_name || b.name, undefined, {
        sensitivity: "base",
        numeric: true,
      });
    const STABILITY_ORDER = ["stable", "beta", "unstable", "alpha"];
    const sorted = [...list];
    if (sortBy === "name") sorted.sort(byName);
    else if (sortBy === "name-desc") sorted.sort((a, b) => byName(b, a));
    else if (sortBy === "stability") {
      sorted.sort((a, b) => {
        const rank = (w: APWorldInfo) => {
          const i = STABILITY_ORDER.indexOf((w.stability || "").toLowerCase());
          return i === -1 ? STABILITY_ORDER.length : i;
        };
        return rank(a) - rank(b) || byName(a, b);
      });
    }
    return sorted;
  }, [available, sortBy, stabilityFilter, installableOnly]);

  const fetchData = () => {
    setLoading(true);
    const calls: Promise<unknown>[] = [getAPWorlds(search)];
    if (generationOn) calls.push(getInstalledAPWorlds());
    Promise.all(calls)
      .then((results) => {
        setAvailable(results[0] as APWorldInfo[]);
        if (generationOn) setInstalled((results[1] as InstalledAPWorld[]) ?? []);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load APWorlds"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchData, 200);
    return () => clearTimeout(debounceRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, generationOn]);

  // Deep link: /apworlds?build=<name> opens the guided YAML builder for
  // that world straight away, same handler as clicking "Create YAML" on
  // its card. Optional &version=<version> pins a specific version; without
  // it, the world's latest (versions[0], the index's own sort order) is
  // used. Guards on a ref (not state) so it fires exactly once per page
  // load, not every time `available` refetches (e.g. after handleRefresh)
  // or the user closes the modal.
  const autoBuildTriggered = useRef(false);
  useEffect(() => {
    if (autoBuildTriggered.current) return;
    if (typeof window === "undefined" || available.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const buildParam = params.get("build");
    if (!buildParam) return;
    autoBuildTriggered.current = true;
    const versionParam = params.get("version");
    const world = available.find((w) => w.name === buildParam);
    const target = versionParam
      ? world?.versions.find((v) => v.version === versionParam)
      : world?.versions[0];
    if (world && target) {
      handleBuild(world.name, target.version);
    } else if (world && versionParam) {
      setError(`APWorld "${buildParam}" has no version "${versionParam}" to build a YAML for.`);
    } else {
      setError(`No APWorld named "${buildParam}" was found to build a YAML for.`);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [available]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      await refreshAPWorldIndex();
      fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const handleInstall = async (name: string, version: string) => {
    setInstalling(`${name}@${version}`);
    setError("");
    try {
      await installAPWorld(name, version);
      const i = await getInstalledAPWorlds();
      setInstalled(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Install failed");
    } finally {
      setInstalling(null);
    }
  };

  const handleRemove = async (name: string) => {
    setError("");
    try {
      await removeAPWorld(name);
      const i = await getInstalledAPWorlds();
      setInstalled(i);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Remove failed");
    }
  };

  return (
    <div className="apworlds-page">
      <div className="page-header">
        <div>
          <h1>APWorlds</h1>
          <p className="muted apworlds-page-sub">
            Sourced from{" "}
            <a href="https://github.com/dowlle/Archipelago-index" target="_blank" rel="noreferrer">
              dowlle/Archipelago-index
            </a>
            . Each card lists every version available for that game; click Download to grab the
            .apworld for local install, or use a room's Settings to pin a version for your players.
          </p>
        </div>
        {isAdmin && (
          <button className="btn" onClick={handleRefresh} disabled={refreshing}>
            {refreshing ? "Fetching index..." : "Refresh index"}
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      <div className="apworld-controls">
        <input
          type="search"
          placeholder="Search by game name or apworld key..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="apworld-search"
        />
        <label className="apworld-control">
          <span>Sort</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}>
            <option value="name">Name (A to Z)</option>
            <option value="name-desc">Name (Z to A)</option>
            <option value="stability">Stability</option>
          </select>
        </label>
        {stabilityValues.length > 0 && (
          <label className="apworld-control">
            <span>Stability</span>
            <select
              value={stabilityFilter}
              onChange={(e) => setStabilityFilter(e.target.value)}
            >
              <option value="">Any</option>
              {stabilityValues.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
              <option value="__unset__">Not recorded</option>
            </select>
          </label>
        )}
        <label className="apworld-check">
          <input
            type="checkbox"
            checked={installableOnly}
            onChange={(e) => setInstallableOnly(e.target.checked)}
          />
          <span>Installable only</span>
        </label>
      </div>

      {loading ? (
        <p className="loading">Loading...</p>
      ) : available.length === 0 ? (
        <p className="muted">No APWorlds found. Try refreshing the index.</p>
      ) : visible.length === 0 ? (
        <p className="muted">
          No APWorlds match these filters.{" "}
          <button
            type="button"
            className="yaml-builder-desc-toggle"
            onClick={() => { setStabilityFilter(""); setInstallableOnly(false); }}
          >
            Clear filters
          </button>
        </p>
      ) : (
        <>
          <p className="muted apworlds-count">
            {visible.length === available.length
              ? `${available.length} APWorlds`
              : `${visible.length} of ${available.length} APWorlds`}
          </p>
          <div className="apworlds-grid">
            {visible.map((w) => (
              <WorldCard
                key={w.name}
                world={w}
                installed={installedMap.get(w.name)}
                installingVersion={
                  installing && installing.startsWith(`${w.name}@`)
                    ? installing.slice(w.name.length + 1)
                    : null
                }
                generationOn={generationOn}
                onInstall={handleInstall}
                onRemove={handleRemove}
                onBuild={handleBuild}
                buildingVersion={
                  building && building.startsWith(`${w.name}@`)
                    ? building.slice(w.name.length + 1)
                    : null
                }
              />
            ))}
          </div>
        </>
      )}

      {/* FEAT-38 (§2.5a): guided builder for the version the user picked.
          No direct submit action here - the review step offers Download
          (always, for everyone via YamlBuilder) plus, for signed-in users
          only, the RoomAttach actions (add to an open room / create a room).
          Anonymous visitors (the index is public) build + download freely and
          see a sign-in hint in place of the room actions. */}
      <YamlBuilder
        open={builder !== null}
        games={builder ? [builder] : []}
        initialGame={builder?.apworld_name}
        surface="apworlds"
        reviewExtra={(yamlContent) =>
          user ? (
            <RoomAttach
              yamlContent={yamlContent}
              onCreateRoom={(yaml) => {
                setPendingYaml(yaml);
                setCreateRoomOpen(true);
              }}
            />
          ) : (
            <section className="settings-section">
              <h3>Use this YAML</h3>
              <p className="settings-hint" style={{ margin: 0 }}>
                Download the file above and use it in any room.{" "}
                <a href="/api/auth/login?next=/apworlds">Sign in with Discord</a>{" "}
                to add it straight to one of your rooms or start a new room with it.
              </p>
            </section>
          )
        }
        onClose={() => setBuilder(null)}
      />
      <CreateRoomModal
        open={createRoomOpen}
        onClose={() => { setCreateRoomOpen(false); setPendingYaml(null); }}
        onCreated={handleRoomCreated}
      />
    </div>
  );
}
