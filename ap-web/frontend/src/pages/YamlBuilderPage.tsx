import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  createYamlFromEditor,
  getApworldBuilderSchema,
  getMyYamls,
  getRoomBuilderSchemas,
  getMyRooms,
  submitYamlContentToRoom,
  type BuilderSchemaEntry,
  type MyRoom,
  type Room,
  type UserYaml,
  getPublicRoom,
  type PublicRoom,
} from "../api";
import CreateRoomModal from "../components/CreateRoomModal";
import YamlBuilder from "../components/YamlBuilder";
import { useAuth } from "../context/AuthContext";
import { createBuilderAttemptId, trackBuilderFailed } from "../lib/analytics";
import { finishBuilderDraftHandoff, pendingBuilderDraft, signInWithBuilderDraft } from "../lib/builderDraft";
import { yamlOutcome } from "../lib/yamlOutcome";

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
  const [savedSource, setSavedSource] = useState<UserYaml | null>(null);
  const [room, setRoom] = useState<PublicRoom | null>(null);
  const completeRef = useRef<((action: string) => void) | null>(null);
  const [readyDraft, setReadyDraft] = useState("");
  const [draftConflict, setDraftConflict] = useState(false);
  const [versionReview, setVersionReview] = useState<{ saved: UserYaml; target: string; changes: string[] } | null>(null);
  const [versionAccepted, setVersionAccepted] = useState(false);
  const [failedCreatedRoom, setFailedCreatedRoom] = useState<Room | null>(null);
  const [attachmentError, setAttachmentError] = useState("");
  const [attachmentBusy, setAttachmentBusy] = useState(false);
  const selectedVersion = games.find((entry) => entry.apworld_name === apworld)?.version ?? version ?? "room";
  const draftKey = `ap-pie:yaml-builder:${user?.id ?? "anonymous"}:${context}:${roomId || "standalone"}:${apworld}:${selectedVersion}${sourceId ? `:saved:${sourceId}` : ""}`;

  useEffect(() => {
    if (loading || !identityReady) return;
    const timer = window.setTimeout(() => {
    const incoming = pendingBuilderDraft(draftKey);
    if (incoming && sessionStorage.getItem(draftKey) && sessionStorage.getItem(draftKey) !== incoming) {
      setDraftConflict(true);
      return;
    }
    if (incoming) finishBuilderDraftHandoff(draftKey, true);
    setReadyDraft(draftKey);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [draftKey, loading, identityReady]);
  const failedLoadAttemptRef = useRef(createBuilderAttemptId());

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
    failedLoadAttemptRef.current = createBuilderAttemptId();

    const run = async () => {
      setLoading(true);
      setError("");
      setInitialYaml(null);
      setInitialValues(null);
      setInitialPlayerName(null);
      setSavedSource(null);
      if (!roomId) setRoom(null);
      if ((context === "public-room" || context === "host-room") && !roomId) {
        throw new Error("This builder link is missing its room.");
      }
      if (context === "standalone" && choosing) {
        throw new Error("Choose a game from the APWorld index before opening the builder.");
      }
      if (roomId) {
        const details = await getPublicRoom(roomId);
        if (!cancelled) setRoom(details);
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
        const target = buildable.find(entry => entry.apworld_name === apworld)!;
        if (!cancelled) setSavedSource(context === "standalone" && saved.version === target.version ? saved : null);
        if (saved.version !== target.version) {
          const changes: string[] = [];
          let previous: BuilderSchemaEntry | null = null;
          try { previous = await loadStandaloneSchema(saved.apworld_name, saved.version); }
          catch { changes.push("The original version's schema is unavailable. Compare your saved values carefully; its file remains in My YAMLs."); }
          const before = previous?.schema?.options ?? [];
          const after = target.schema!.options;
          for (const option of before) {
            const next = after.find(item => item.name === option.name);
            if (!next) changes.push(`${option.display_name || option.name}: no longer offered by the new form; a form-built copy will omit it.`);
            else {
              if (JSON.stringify([option.type, option.min, option.max, option.choices, option.valid_keys]) !== JSON.stringify([next.type, next.min, next.max, next.choices, next.valid_keys])) changes.push(`${option.display_name || option.name}: accepted values or control type changed. Review your current value.`);
              if (JSON.stringify(option.default) !== JSON.stringify(next.default)) changes.push(`${option.display_name || option.name}: default changed from ${JSON.stringify(option.default)} to ${JSON.stringify(next.default)}. Your saved value is retained where supported.`);
            }
          }
          for (const option of after) if (before.length && !before.some(old => old.name === option.name)) changes.push(`${option.display_name || option.name}: new option, initially ${JSON.stringify(option.default)}.`);
          if (!cancelled) { setVersionReview({ saved, target: target.version, changes }); setVersionAccepted(false); }
        } else if (!cancelled) { setVersionReview(null); setVersionAccepted(false); }
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
        if (!cancelled) {
          const message = reason instanceof Error ? reason.message : "Failed to load the builder";
          const failure = message.includes("No YAML option forms") || message.includes("does not offer")
            ? "schema_unsupported"
            : "schema_load_failed";
          trackBuilderFailed(
            apworld || "unknown", version || "unknown", "preset", failure,
            failedLoadAttemptRef.current, roomId || undefined,
          );
          setError(message);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apworld, choosing, context, identityReady, roomId, sourceId, version]);

  const handleRoomCreated = async (room: Room) => {
    setCreateRoomOpen(false);
    const yaml = pendingYaml;
    setAttachmentBusy(true);
    if (yaml) {
      try {
        await submitYamlContentToRoom(room.id, yaml);
        completeRef.current?.("create_room");
      } catch (reason) {
        setFailedCreatedRoom(room);
        setAttachmentError(`The room was created, but adding this YAML failed: ${reason instanceof Error ? reason.message : "submission failed"}. Your YAML is still here.`);
        setAttachmentBusy(false);
        return;
      }
    }
    setPendingYaml(null);
    setAttachmentBusy(false);
    navigate(`/rooms/${room.id}`);
  };

  if (loading || (!error && readyDraft !== draftKey && !draftConflict)) {
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
        {room && <p>For {room.name} · {room.status} · APWorld v{selectedVersion}{room.submit_deadline && <> · Deadline {new Date(room.submit_deadline).toLocaleString()}</>}</p>}
        <p className="error">{error}</p>
        <Link className="btn" to={returnPath}>Go back</Link>
        <button className="btn" onClick={() => location.reload()}>Try again</button>
        <a className="btn" href="/guides/setting-up-your-yaml">Get a template another way</a>
        {sourceId && <Link className="btn" to="/my/yamls">Return to your saved YAMLs</Link>}
      </div>
    );
  }
  if (draftConflict) return <section className="yaml-builder-route-state">
    <h1>Choose which draft to continue</h1>
    <p>You have an existing signed-in draft and the draft you just brought through sign-in. Neither has been overwritten.</p>
    <button className="btn btn-primary" onClick={() => { finishBuilderDraftHandoff(draftKey, true); setDraftConflict(false); setReadyDraft(draftKey); }}>Continue the draft from before sign-in</button>
    <button className="btn" onClick={() => { finishBuilderDraftHandoff(draftKey, false); setDraftConflict(false); setReadyDraft(draftKey); }}>Keep my signed-in draft</button>
  </section>;
  if (versionReview && !versionAccepted) return <section className="yaml-builder-route-state">
    <h1>Review the version change</h1>
    <p>{versionReview.saved.label || versionReview.saved.apworld_name}: v{versionReview.saved.version} → v{versionReview.target}{room ? ` for ${room.name}` : ""}.</p>
    <p>Your original stays unchanged in My YAMLs. Continue to review a separate copy against the new version. Nothing is submitted automatically.</p>
    {versionReview.changes.length ? <ul>{versionReview.changes.map((change, index) => <li key={index}>{change}</li>)}</ul> : <p>No differences were found in the available option metadata. Generation behavior may still differ.</p>}
    <button className="btn btn-primary" onClick={() => setVersionAccepted(true)}>Review a copy with v{versionReview.target}</button>
    <Link className="btn" to={`/yaml-builder/${encodeURIComponent(versionReview.saved.apworld_name)}?version=${encodeURIComponent(versionReview.saved.version)}&from=${versionReview.saved.id}`}>Keep v{versionReview.saved.version}</Link>
    {room && <Link className="btn" to={returnPath}>Return to {room.name}</Link>}
  </section>;

  const submit = context === "public-room"
    ? {
        label: "Submit to this room",
        run: async (yamlContent: string) => {
          const result = await submitYamlContentToRoom(roomId, yamlContent);
          return `Submitted ${yamlOutcome(result)}`;
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
            return `Created ${yamlOutcome(result)}`;
          },
        }
      : undefined;

  return (
    <>
      {failedCreatedRoom && <section className="settings-section" role="alert">
        <p>{attachmentError}</p>
        <button className="btn" disabled={attachmentBusy} onClick={() => void handleRoomCreated(failedCreatedRoom)}>Retry adding YAML</button>
        <Link to={`/r/${failedCreatedRoom.id}`}>Open the created room</Link>
      </section>}
      {room && <aside className="yaml-room-context" aria-label="Submission destination">
        <strong>For {room.name}</strong> · {room.status} · APWorld v{selectedVersion}
        {room.submit_deadline && <> · Deadline {new Date(room.submit_deadline).toLocaleString()}</>}
        <Link to={returnPath}>Return to room</Link>
        <span>Review and submit here. You can return to the room to check validation and edit your submission.</span>
      </aside>}
      <YamlBuilder
        key={draftKey}
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
        savedSource={savedSource}
        onSaved={setSavedSource}
        submit={submit}
        reviewExtra={context === "standalone" ? (yamlContent, _playerName, complete) => (
          user ? (
            <RoomAttach
              yamlContent={yamlContent}
              canCreateRoom={!user.room_creation_blocked}
              onCompleted={() => complete("add_to_room")}
              onCreateRoom={(yaml) => {
                setPendingYaml(yaml);
                completeRef.current = complete;
                setCreateRoomOpen(true);
              }}
            />
          ) : (
            <section className="settings-section">
              <h3>Use this YAML</h3>
              <p className="settings-hint" style={{ margin: 0 }}>
                Download it for any room, or{" "}
                <a href={`/api/auth/login?next=${encodeURIComponent(location.pathname + location.search)}`} onClick={(event) => { event.preventDefault(); signInWithBuilderDraft(draftKey); }}>
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
        onClose={() => setCreateRoomOpen(false)}
        onCreated={handleRoomCreated}
      />
    </>
  );
}

function RoomAttach({
  yamlContent,
  canCreateRoom,
  onCreateRoom,
  onCompleted,
}: {
  yamlContent: string;
  canCreateRoom: boolean;
  onCreateRoom: (yamlContent: string) => void;
  onCompleted: () => void;
}) {
  const [rooms, setRooms] = useState<MyRoom[]>([]);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState<{ roomId: string; message: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMyRooms()
      .then((result) => { if (!cancelled) setRooms(result.filter((room) => room.status === "open" && (!room.submit_deadline || Date.parse(room.submit_deadline) > Date.now()))); })
      .catch(() => { if (!cancelled) setError("Could not load your rooms. Try reopening the builder."); });
    return () => { cancelled = true; };
  }, []);

  const handleAdd = async () => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const result = await submitYamlContentToRoom(selected, yamlContent);
      onCompleted();
      setAdded({
        roomId: selected,
        message: `Added ${yamlOutcome(result)}`,
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
          ✓ {added.message}. <Link to={`/r/${added.roomId}`}>Open the room</Link>
        </p>
      ) : (
        <>
          <div className="settings-controls">
            <select aria-label="Room to send YAML to" value={selected} onChange={(event) => setSelected(event.target.value)}>
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
            Join a room from its shared link to see it here. <Link to="/my/rooms">My rooms</Link>.{" "}
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
