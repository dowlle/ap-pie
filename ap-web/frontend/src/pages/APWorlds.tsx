import { useEffect, useMemo, useRef, useState } from "react";
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
          {!world.is_builtin && world.supported && (
            <span className="badge badge-save">Community</span>
          )}
          {world.tags.map((t) => (
            <span key={t} className="tag" title={TAG_DESCRIPTIONS[t]}>{t}</span>
          ))}
        </div>
      </header>

      {world.home && (
        <a href={world.home} target="_blank" rel="noreferrer" className="apworld-card-home">
          {world.home}
        </a>
      )}

      {builtinOnly ? (
        <p className="apworld-card-note muted">
          No external versions in the index - this APWorld ships with Archipelago itself.
        </p>
      ) : (
        <ul className="apworld-version-list">
          {versions.map((v) => (
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
