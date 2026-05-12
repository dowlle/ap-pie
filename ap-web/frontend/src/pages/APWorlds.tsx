import { useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import {
  getAPWorlds,
  getInstalledAPWorlds,
  installAPWorld,
  removeAPWorld,
  refreshAPWorldIndex,
  type APWorldInfo,
  type APWorldVersion,
  type InstalledAPWorld,
} from "../api";
import { useFeature } from "../context/FeaturesContext";
import { useAuth } from "../context/AuthContext";

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
 * version's download URL when the index points at GitHub releases.
 * Returns null if no version has a GitHub URL we can parse. */
function deriveGitHubRepoUrl(versions: APWorldVersion[]): string | null {
  for (const v of versions) {
    if (!v.url) continue;
    const m = v.url.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)\//i);
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
}: {
  world: APWorldInfo;
  v: APWorldVersion;
  installed: InstalledAPWorld | undefined;
  installing: boolean;
  generationOn: boolean;
  onInstall: (name: string, version: string) => void;
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
        {isCurrent && <span className="badge badge-done apworld-version-current">installed</span>}
      </span>
      <span className="apworld-version-actions">
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
  let homeIcon: { node: ReactElement; href: string; title: string; label: string; kind: "discord" | "github" | "archipelago" } | null = null;
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
    }
  }

  const textHome = world.home && !homeIcon ? world.home : null;

  // Derive a GitHub repo from version URLs when we don't already have
  // a GitHub icon from `home`. This is the trust anchor — it points at
  // wherever the index actually pulls the .apworld from.
  const derivedRepo =
    homeIcon?.kind === "github" ? null : deriveGitHubRepoUrl(world.versions);

  const hasIcons = Boolean(homeIcon) || Boolean(derivedRepo) || Boolean(world.setup_guide) || Boolean(world.tracker);

  return (
    <>
      {textHome && (
        <a href={textHome} target="_blank" rel="noreferrer" className="apworld-card-home">
          {textHome}
        </a>
      )}
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
}: {
  world: APWorldInfo;
  installed: InstalledAPWorld | undefined;
  installingVersion: string | null;
  generationOn: boolean;
  onInstall: (name: string, version: string) => void;
  onRemove: (name: string) => void;
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

  const installedMap = useMemo(
    () => new Map(installed.map((w) => [w.name, w])),
    [installed],
  );

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

      <input
        type="search"
        placeholder="Search by game name or apworld key..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="apworld-search"
      />

      {loading ? (
        <p className="loading">Loading...</p>
      ) : available.length === 0 ? (
        <p className="muted">No APWorlds found. Try refreshing the index.</p>
      ) : (
        <>
          <p className="muted apworlds-count">{available.length} APWorlds</p>
          <div className="apworlds-grid">
            {available.map((w) => (
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
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
