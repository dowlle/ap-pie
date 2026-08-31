import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  createYamlFromEditor,
  getApworldBuilderSchema,
  getMyYamls,
  getRoomBuilderSchemas,
  getRooms,
  submitYamlContentToRoom,
  type BuilderSchemaEntry,
  type Room,
} from "../api";
import CreateRoomModal from "../components/CreateRoomModal";
import YamlBuilder from "../components/YamlBuilder";
import { useAuth } from "../context/AuthContext";

type BuilderContext = "standalone" | "public-room" | "host-room";

function contextFrom(value: string | null): BuilderContext {
  if (value === "public-room" || value === "host-room") return value;
  return "standalone";
}

async function loadStandaloneSchema(name: string, version?: string) {
  let entry = await getApworldBuilderSchema(name, version);
  for (let attempt = 0; entry.pending && attempt < 6; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
    entry = await getApworldBuilderSchema(name, version);
  }
  return entry;
}

async function loadRoomSchemas(roomId: string) {
  let entries = await getRoomBuilderSchemas(roomId);
  for (let attempt = 0; entries.some((entry) => entry.pending) && attempt < 4; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1500));
    entries = await getRoomBuilderSchemas(roomId);
  }
  return entries;
}

export default function YamlBuilderPage() {
  const { apworld = "" } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const context = contextFrom(searchParams.get("context"));
  const roomId = searchParams.get("room") ?? "";
  const version = searchParams.get("version") ?? undefined;
  const sourceId = searchParams.get("from");
  const choosing = apworld === "select";

  const [games, setGames] = useState<BuilderSchemaEntry[]>([]);
  const [initialYaml, setInitialYaml] = useState<string | null>(null);
  const [initialValues, setInitialValues] = useState<Record<string, unknown> | null>(null);
  const [initialPlayerName, setInitialPlayerName] = useState<string | null>(null);
  const identityReady = !authLoading;
  const defaultPlayerName = identityReady
    ? user?.discord_username?.trim().slice(0, 16) || null
    : null;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createRoomOpen, setCreateRoomOpen] = useState(false);
  const [pendingYaml, setPendingYaml] = useState<string | null>(null);

  const returnPath = useMemo(() => {
    if (context === "public-room" && roomId) return `/r/${roomId}`;
    if (context === "host-room" && roomId) return `/rooms/${roomId}`;
    if (sourceId) return "/my/yamls";
    return "/apworlds";
  }, [context, roomId, sourceId]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "YAML Builder | Archipelago Pie";
    let robots = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    const priorRobots = robots?.content;
    if (!robots) {
      robots = document.createElement("meta");
      robots.name = "robots";
      document.head.appendChild(robots);
    }
    robots.content = "noindex, nofollow";
    return () => {
      document.title = previousTitle;
      if (priorRobots === undefined) robots?.remove();
      else if (robots) robots.content = priorRobots;
    };
  }, []);

  useEffect(() => {
    if (!identityReady) return;
    let cancelled = false;

    const run = async () => {
      if ((context === "public-room" || context === "host-room") && !roomId) {
        throw new Error("This builder link is missing its room.");
      }
      if (context === "standalone" && choosing) {
        throw new Error("Choose a game from the APWorld index before opening the builder.");
      }

      const entries = context === "standalone"
        ? [await loadStandaloneSchema(apworld, version)]
        : await loadRoomSchemas(roomId);
      const buildable = entries.filter((entry) => entry.schema !== null && !entry.pending);
      if (buildable.length === 0) {
        throw new Error("No YAML option forms are available for this builder link.");
      }
      if (!choosing && !buildable.some((entry) => entry.apworld_name === apworld)) {
        throw new Error(`This room does not offer a buildable APWorld named “${apworld}”.`);
      }
      if (!cancelled) setGames(buildable);

      if (sourceId) {
        const saved = (await getMyYamls()).find((item) => String(item.id) === sourceId);
        if (!saved) throw new Error("That saved YAML could not be found.");
        if (saved.kind === "advanced" && saved.yaml_content) {
          if (!cancelled) setInitialYaml(saved.yaml_content);
        } else if (saved.values) {
          if (!cancelled) {
            setInitialValues(saved.values as Record<string, unknown>);
            setInitialPlayerName(saved.player_name);
          }
        }
      }
    };

    run()
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Failed to load the builder");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apworld, choosing, context, identityReady, roomId, sourceId, version]);

  const handleRoomCreated = async (room: Room) => {
    setCreateRoomOpen(false);
    const yaml = pendingYaml;
    setPendingYaml(null);
    if (yaml) {
      try {
        await submitYamlContentToRoom(room.id, yaml);
      } catch (reason) {
        window.alert(
          `Room created, but the YAML could not be added automatically: ${
            reason instanceof Error ? reason.message : "submission failed"
          }. You can upload it on the room page.`,
        );
      }
    }
    navigate(`/rooms/${room.id}`);
  };

  if (loading) {
    return (
      <div className="yaml-builder-route-state" role="status">
        <h1>Preparing your YAML builder</h1>
        <p>Reading the APWorld options and defaults…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="yaml-builder-route-state">
        <h1>We could not open this builder</h1>
        <p className="error">{error}</p>
        <Link className="btn" to={returnPath}>Go back</Link>
      </div>
    );
  }

  const submit = context === "public-room"
    ? {
        label: "Submit to this room",
        run: async (yamlContent: string) => {
          const result = await submitYamlContentToRoom(roomId, yamlContent);
          return `Submitted ${result.player_name} (${result.game}) - ${result.validation_status}`;
        },
      }
    : context === "host-room"
      ? {
          label: "Add to this room",
          run: async (yamlContent: string, playerName: string, game: string) => {
            const result = await createYamlFromEditor(roomId, {
              player_name: playerName,
              game,
              yaml_content: yamlContent,
            });
            return `Created ${result.player_name} (${result.game}) - ${result.validation_status}`;
          },
        }
      : undefined;
  const selectedVersion = games.find((entry) => entry.apworld_name === apworld)?.version ?? version ?? "room";
  const draftKey = `ap-pie:yaml-builder:${user?.id ?? "anonymous"}:${context}:${roomId || "standalone"}:${apworld}:${selectedVersion}`;

  return (
    <>
      <YamlBuilder
        open
        presentation="page"
        games={games}
        initialGame={choosing ? games[0]?.apworld_name : apworld}
        onGameChange={(name) => {
          if (context === "standalone") return;
          navigate(
            `/yaml-builder/${encodeURIComponent(name)}?context=${context}&room=${encodeURIComponent(roomId)}`,
            { replace: true },
          );
        }}
        surface={context === "standalone" ? "apworlds" : context === "public-room" ? "room_public" : "room_detail"}
        roomId={roomId || undefined}
        initialYaml={initialYaml}
        initialValues={initialValues}
        initialPlayerName={initialPlayerName}
        defaultPlayerName={defaultPlayerName}
        draftKey={draftKey}
        submit={submit}
        reviewExtra={context === "standalone" ? (yamlContent) => (
          user ? (
            <RoomAttach
              yamlContent={yamlContent}
              canCreateRoom={!user.room_creation_blocked}
              onCreateRoom={(yaml) => {
                setPendingYaml(yaml);
                setCreateRoomOpen(true);
              }}
            />
          ) : (
            <section className="settings-section">
              <h3>Use this YAML</h3>
              <p className="settings-hint" style={{ margin: 0 }}>
                Download it for any room, or{" "}
                <a href={`/api/auth/login?next=${encodeURIComponent(location.pathname + location.search)}`}>
                  sign in with Discord
                </a>{" "}
                to add it to one of your rooms.
              </p>
            </section>
          )
        ) : undefined}
        onClose={() => navigate(returnPath)}
      />
      <CreateRoomModal
        open={createRoomOpen}
        onClose={() => { setCreateRoomOpen(false); setPendingYaml(null); }}
        onCreated={handleRoomCreated}
      />
    </>
  );
}

function RoomAttach({
  yamlContent,
  canCreateRoom,
  onCreateRoom,
}: {
  yamlContent: string;
  canCreateRoom: boolean;
  onCreateRoom: (yamlContent: string) => void;
}) {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState<{ roomId: string; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getRooms("open")
      .then((result) => { if (!cancelled) setRooms(result); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const handleAdd = async () => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await submitYamlContentToRoom(selected, yamlContent);
      setAdded({
        roomId: selected,
        message: `Added ${result.player_name} (${result.game}) - ${result.validation_status}`,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to add YAML to the room");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="settings-section">
      <h3>Use this YAML</h3>
      {added ? (
        <p className="settings-aux-note" style={{ margin: 0, color: "var(--green)" }}>
          ✓ {added.message}. <Link to={`/rooms/${added.roomId}`}>Open the room</Link>
        </p>
      ) : (
        <>
          <div className="settings-controls">
            <select value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">{rooms.length ? "Select one of your open rooms…" : "No open rooms"}</option>
              {rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
            </select>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleAdd} disabled={!selected || busy}>
              {busy ? "Adding…" : "Add to room"}
            </button>
            {canCreateRoom && (
              <button type="button" className="btn btn-sm" onClick={() => onCreateRoom(yamlContent)} disabled={busy}>
                Create room with this YAML
              </button>
            )}
          </div>
          <p className="settings-hint">
            {canCreateRoom
              ? "Or download the file and use it anywhere."
              : "New room creation is disabled for this account. You can still add the YAML to an existing room or download it."}
          </p>
          {error && <p className="settings-error" style={{ margin: 0 }}>{error}</p>}
        </>
      )}
    </section>
  );
}
