import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getAPWorlds, getRoomBuilderSchemas, type APWorldInfo } from "../api";
import { useAuth } from "../context/AuthContext";

interface LocalDraft {
  key: string;
  apworld: string;
  version: string;
  playerName: string;
}

function readStandaloneDrafts(userId: number | undefined): LocalDraft[] {
  const drafts: LocalDraft[] = [];
  const owner = String(userId ?? "anonymous");
  for (let index = 0; index < sessionStorage.length; index += 1) {
    const key = sessionStorage.key(index);
    if (!key?.startsWith(`ap-pie:yaml-builder:${owner}:standalone:`)) continue;
    const parts = key.split(":");
    if (parts.length < 7) continue;
    try {
      const stored = JSON.parse(sessionStorage.getItem(key) ?? "{}") as { playerName?: string };
      drafts.push({
        key,
        apworld: parts[5],
        version: parts.slice(6).join(":"),
        playerName: stored.playerName || "Player1",
      });
    } catch {
      // A damaged local draft should not block the landing page.
    }
  }
  return drafts.slice(0, 4);
}

function latestBuildVersion(world: APWorldInfo): string | null {
  return world.downloadable_versions[0]?.version ?? null;
}

export default function YamlBuilderLanding() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const requestedContext = searchParams.get("context");
  const requestedRoomId = searchParams.get("room") ?? "";
  const roomContext = requestedContext === "host-room" || requestedContext === "public-room"
    ? requestedContext
    : null;
  const [query, setQuery] = useState("");
  const [worlds, setWorlds] = useState<APWorldInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<LocalDraft[]>([]);
  const [roomBuildableNames, setRoomBuildableNames] = useState<Set<string> | null>(null);

  useEffect(() => {
    if (!roomContext || !requestedRoomId) return;
    let cancelled = false;
    getRoomBuilderSchemas(requestedRoomId)
      .then((entries) => {
        if (!cancelled) {
          setRoomBuildableNames(new Set(
            entries.filter((entry) => entry.schema !== null && !entry.pending).map((entry) => entry.apworld_name),
          ));
        }
      })
      .catch(() => { if (!cancelled) setRoomBuildableNames(new Set()); });
    return () => { cancelled = true; };
  }, [requestedRoomId, roomContext]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDrafts(readStandaloneDrafts(user?.id)), 0);
    return () => window.clearTimeout(timer);
  }, [user?.id]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      getAPWorlds(query.trim())
        .then((result) => {
          if (!cancelled) {
            setWorlds(result);
            setError("");
          }
        })
        .catch((reason) => {
          if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load APWorlds");
        })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 180);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [query]);

  const visible = useMemo(() => {
    const buildable = worlds.filter((world) =>
      !world.disabled &&
      latestBuildVersion(world) &&
      (!roomContext || !requestedRoomId || roomBuildableNames?.has(world.name)),
    );
    if (query.trim()) return buildable.slice(0, 18);
    return [...buildable]
      .sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""))
      .slice(0, 12);
  }, [query, requestedRoomId, roomBuildableNames, roomContext, worlds]);

  const openWorld = (world: APWorldInfo) => {
    const version = latestBuildVersion(world);
    if (!version) return;
    const params = new URLSearchParams({ version });
    if (roomContext && requestedRoomId) {
      params.set("context", roomContext);
      params.set("room", requestedRoomId);
    }
    navigate(`/yaml-builder/${encodeURIComponent(world.name)}?${params.toString()}`);
  };

  const deleteDraft = (draft: LocalDraft) => {
    const label = draft.apworld.replaceAll("_", " ");
    if (!window.confirm(`Delete your ${label} v${draft.version} draft from this browser tab?`)) return;
    sessionStorage.removeItem(draft.key);
    setDrafts((current) => current.filter((item) => item.key !== draft.key));
  };

  return (
    <div className="yaml-builder-landing">
      <header className="yaml-builder-landing-hero">
        <h1>Build a player YAML</h1>
        <p>
          {roomContext
            ? "Pick one of this room's APWorlds, choose its options, and add the finished YAML to the room."
            : "Pick your game, choose its options, and watch the YAML update as you work. Download the finished file or send it to an Archipelago Pie room."}
        </p>
        <label className="yaml-builder-game-search">
          <span>Find your game</span>
          <input
            type="search"
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search Crash Team Racing, Stardew Valley, Pokepelago…"
          />
        </label>
        <div className="yaml-builder-landing-links">
          <Link className="btn" to="/apworlds">Browse the full APWorld index</Link>
          <a className="btn" href="/guides/getting-started">How Archipelago works</a>
          {user && <Link className="btn" to="/my/yamls">My saved YAMLs</Link>}
        </div>
      </header>

      {drafts.length > 0 && (
        <section className="yaml-builder-landing-section" aria-labelledby="builder-drafts-title">
          <div className="yaml-builder-section-head">
            <div>
              <h2 id="builder-drafts-title">Continue your draft</h2>
              <p>Unfinished work saved in this browser tab.</p>
            </div>
          </div>
          <div className="yaml-builder-draft-grid">
            {drafts.map((draft) => (
              <article key={draft.key} className="yaml-builder-draft-card">
                <div>
                  <strong>{draft.apworld.replaceAll("_", " ")}</strong>
                  <span>{draft.playerName} · v{draft.version}</span>
                </div>
                <div className="yaml-builder-draft-actions">
                  <Link
                    className="btn btn-sm btn-primary"
                    to={`/yaml-builder/${encodeURIComponent(draft.apworld)}?version=${encodeURIComponent(draft.version)}`}
                  >
                    Continue
                  </Link>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    aria-label={`Delete ${draft.apworld.replaceAll("_", " ")} draft`}
                    onClick={() => deleteDraft(draft)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="yaml-builder-landing-section" aria-labelledby="builder-games-title">
        <div className="yaml-builder-section-head">
          <div>
            <h2 id="builder-games-title">{query.trim() ? "Search results" : "Recently updated games"}</h2>
            <p>{query.trim() ? "Choose the APWorld version shown to open its option form." : "A few places to start. Search above for any other game."}</p>
          </div>
          {!loading && <span className="muted">{visible.length} shown</span>}
        </div>
        {error && <p className="error">{error}</p>}
        {loading ? (
          <p className="loading">Loading games…</p>
        ) : visible.length === 0 ? (
          <p className="yaml-builder-empty">No buildable APWorlds match that search.</p>
        ) : (
          <div className="yaml-builder-game-grid">
            {visible.map((world) => {
              const version = latestBuildVersion(world)!;
              return (
                <button key={world.name} type="button" className="yaml-builder-game-card" onClick={() => openWorld(world)}>
                  <span className="yaml-builder-game-card-main">
                    <strong>{world.display_name || world.game_name}</strong>
                    <code>{world.name}</code>
                  </span>
                  <span className="yaml-builder-game-card-meta">
                    {world.stability && <span className="badge">{world.stability}</span>}
                    <span>v{version}</span>
                    <span aria-hidden="true">→</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="yaml-builder-explainer" aria-labelledby="builder-explainer-title">
        <div>
          <h2 id="builder-explainer-title">One file describing one world</h2>
          <p>
            A player YAML contains your exact slot name, game, APWorld version, and chosen randomizer options.
            A host usually collects one for every world before generating the multiworld.
          </p>
        </div>
        <ol>
          <li><strong>Choose a game and version.</strong><span>Match the version requested by your host.</span></li>
          <li><strong>Set your player name and options.</strong><span>The live document shows exactly what will be saved.</span></li>
          <li><strong>Download or submit.</strong><span>Send the file through the collector your host provides.</span></li>
        </ol>
      </section>
    </div>
  );
}
