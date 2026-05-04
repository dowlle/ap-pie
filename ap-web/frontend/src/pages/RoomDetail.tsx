import { useEffect, useState, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  getRoom, uploadYaml, removeYaml, closeRoom, reopenRoom, generateRoom, launchRoom, getRoomPatches, getRoomSpoiler, testGenerateRoom,
  stopRoom, deleteRoom, updateRoom, updateRoomYaml, setYamlValidation,
  getGenerationJob, getLatestGenerationJob,
  type Room, type GenerationJob, type ValidationStatus,
} from "../api";
import {
  cleanYamlFilename,
  filterAndSortYamls,
  nextSort,
  sortIndicator,
  ariaSortValue,
  type YamlSort,
  type YamlSortKey,
} from "../lib/yamlTable";
import YamlEditor from "../components/YamlEditor";
import LiveTracker from "../components/LiveTracker";
import ItemTracker from "../components/ItemTracker";
import ShareGame from "../components/ShareGame";
import DropOverlay from "../components/DropOverlay";
import YamlModal from "../components/YamlModal";
import CopyButton from "../components/CopyButton";
import RoomSettingsModal from "../components/RoomSettingsModal";
import GameCell from "../components/GameCell";
import { useAPWorldLookup } from "../lib/apworldLookup";
import { getRoomAPWorlds } from "../api";
import { useFileDropZone } from "../lib/useFileDropZone";
import { useFeature } from "../context/FeaturesContext";
import { useAuth } from "../context/AuthContext";
import { usePageTitle } from "../lib/usePageTitle";
import {
  formatDeadlineAbsolute,
  formatDeadlineCountdown,
  isoToLocalInputValue,
  localInputValueToIso,
} from "../lib/roomDeadline";

function SharePublicRoomButton({ roomId }: { roomId: string }) {
  const url = typeof window !== "undefined" ? `${window.location.origin}/r/${roomId}` : `/r/${roomId}`;
  return (
    <CopyButton
      value={url}
      label="Share"
      copiedLabel="Link copied!"
    />
  );
}

function ValidationBadge({ status, error }: { status: ValidationStatus; error: string | null }) {
  switch (status) {
    case "validated":
      return <span className="badge badge-done">Validated</span>;
    case "manually_validated":
      return <span className="badge badge-trusted" title="Marked valid by host (validator override)">Host-trusted</span>;
    case "unsupported":
      return <span className="badge badge-warn" title="Game's apworld is not installed on this server">Unsupported</span>;
    case "failed":
      return <span className="badge badge-error" title={error ?? ""}>Failed</span>;
    case "unknown":
    default:
      return <span className="badge badge-pending">Pending</span>;
  }
}

function EditableRoomHeader({
  room,
  onUpdate,
  onDelete,
  onOpenSettings,
  shareControl,
}: {
  room: Room;
  onUpdate: () => void;
  onDelete: () => void;
  onOpenSettings: () => void;
  shareControl: React.ReactNode;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(room.name);
  const [description, setDescription] = useState(room.description ?? "");
  const [deadlineLocal, setDeadlineLocal] = useState(isoToLocalInputValue(room.submit_deadline));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Re-tick every 30s so the deadline countdown stays fresh without a full
  // refresh. Running while not editing too - display block uses this.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!room.submit_deadline) return;
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, [room.submit_deadline]);

  const startEdit = () => {
    setName(room.name);
    setDescription(room.description ?? "");
    setDeadlineLocal(isoToLocalInputValue(room.submit_deadline));
    setErr("");
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setErr("");
  };

  const save = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setErr("Name can't be empty");
      return;
    }
    setSaving(true);
    setErr("");
    try {
      await updateRoom(room.id, {
        name: trimmed,
        description,
        submit_deadline: localInputValueToIso(deadlineLocal),
      });
      setEditing(false);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const deadlineLine = room.submit_deadline ? (
    <span title={formatDeadlineAbsolute(room.submit_deadline)}>
      Auto-close: {formatDeadlineAbsolute(room.submit_deadline)} ({formatDeadlineCountdown(room.submit_deadline, now)})
    </span>
  ) : null;

  if (!editing) {
    return (
      <div className="detail-header">
        <div className="page-header">
          <h1>{room.name}</h1>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <span className={`badge ${room.status === "playing" ? "badge-done" : "badge-save"}`}>
              {room.status}
            </span>
            {shareControl}
            <button className="btn btn-sm" onClick={startEdit}>Edit</button>
            <button className="btn btn-sm" onClick={onOpenSettings}>Settings</button>
            <button className="btn btn-sm btn-danger" onClick={onDelete}>Delete</button>
          </div>
        </div>
        <p className="play-hint detail-meta-line">
          Hosted by <strong>{room.host_name}</strong>
          {room.claim_mode && <> · <strong>claim mode</strong></>}
          {" · "}
          {(room.yamls?.length ?? 0)} {(room.yamls?.length ?? 0) === 1 ? "slot" : "slots"}
          {room.max_players > 0 && <> / cap {room.max_players}</>}
          {room.max_yamls_per_user > 0 && <> · {room.max_yamls_per_user} per Discord user</>}
          {room.seed && <> · seed <code>{room.seed}</code></>}
          {deadlineLine && <> · {deadlineLine}</>}
        </p>
        {room.description && <p className="muted" style={{ marginTop: "0.5rem" }}>{room.description}</p>}
      </div>
    );
  }

  return (
    <div className="detail-header">
      <div className="room-edit-card">
        <input
          type="text"
          className="room-edit-title"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Room name"
          disabled={saving}
          autoFocus
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          rows={2}
          disabled={saving}
        />
        <label
          className="room-edit-row"
          title="Optional. The room auto-closes at this date/time in your local timezone. You can still close it manually before then."
        >
          <span className="room-edit-label">Auto-close at</span>
          <input
            type="datetime-local"
            value={deadlineLocal}
            onChange={(e) => setDeadlineLocal(e.target.value)}
            disabled={saving}
          />
          {deadlineLocal && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setDeadlineLocal("")}
              disabled={saving}
              title="Clear the deadline"
            >
              Clear
            </button>
          )}
        </label>
        <div className="room-edit-actions">
          <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          <button className="btn btn-sm" onClick={cancel} disabled={saving}>Cancel</button>
          {err && <span className="error">{err}</span>}
        </div>
      </div>
      <p className="play-hint detail-meta-line" style={{ marginTop: "0.5rem" }}>
        Hosted by <strong>{room.host_name}</strong>
        {room.claim_mode && <> · <strong>claim mode</strong></>}
        {room.seed && <> · seed <code>{room.seed}</code></>}
      </p>
    </div>
  );
}

export default function RoomDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const generationOn = useFeature("generation");
  const apworldLookup = useAPWorldLookup();
  // FEAT-28 v2: fetch the room's pinned APWorld versions so the YAML
  // table's Version column can flag mismatches in orange. Refreshes
  // on the same trigger as the room data so the warnings stay current
  // after auto-pin / manual pin changes.
  const [pinByApworld, setPinByApworld] = useState<Map<string, string>>(new Map());
  const { user } = useAuth();
  const [room, setRoom] = useState<Room | null>(null);
  const [patches, setPatches] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [genLog, setGenLog] = useState("");
  const [genJob, setGenJob] = useState<GenerationJob | null>(null);
  const [viewingYamlId, setViewingYamlId] = useState<number | null>(null);
  const [yamlSearch, setYamlSearch] = useState("");
  const [yamlSort, setYamlSort] = useState<YamlSort | null>(null);

  usePageTitle(room?.name);
  const [showEditor, setShowEditor] = useState(false);
  const [trackerTab, setTrackerTab] = useState<"progress" | "items">("progress");
  const [spoilerLog, setSpoilerLog] = useState<string | null>(null);
  const [spoilerLoading, setSpoilerLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () => {
    if (!id) return;
    getRoom(id).then((r) => {
      setRoom(r);
      if (r.seed) getRoomPatches(id).then(setPatches);
      if (r.generation_log) setGenLog(r.generation_log);
    }).catch(() => setError("Room not found"));
    // FEAT-28 v2: keep the pin map in sync. Failure is silent - the
    // Version column degrades to "no warnings" rather than blocking
    // the page on a pin fetch.
    getRoomAPWorlds(id)
      .then((entries) => {
        const m = new Map<string, string>();
        for (const e of entries) {
          if (e.apworld_name && e.selected_version) {
            m.set(e.apworld_name, e.selected_version);
          }
        }
        setPinByApworld(m);
      })
      .catch(() => {});
  };

  useEffect(() => { refresh(); }, [id]);

  // On mount (and after refresh), pick up any in-flight or recently-finished
  // generation job for this room. Handles the page-reload-during-gen case
  // where the user kicked off a job, navigated away, and came back.
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getLatestGenerationJob(id).then((job) => {
      if (cancelled || job.status === "none") return;
      const live = job as GenerationJob;
      setGenJob(live);
      if (live.log) setGenLog(live.log);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [id]);

  // Poll the active job until it terminates.
  useEffect(() => {
    if (!id || !genJob) return;
    if (genJob.status !== "queued" && genJob.status !== "running") return;
    const tick = async () => {
      try {
        const fresh = await getGenerationJob(id, genJob.id);
        setGenJob(fresh);
        if (fresh.log) setGenLog(fresh.log);
        if (fresh.status === "succeeded" || fresh.status === "failed" || fresh.status === "cancelled") {
          if (fresh.status === "failed" && fresh.error) {
            setError(fresh.error);
          }
          refresh();
        }
      } catch {
        /* transient errors - keep polling */
      }
    };
    const interval = setInterval(tick, 2000);
    return () => clearInterval(interval);
  }, [id, genJob?.id, genJob?.status]);

  // NOTE: hooks above this line, plain functions / early returns below.
  // useFileDropZone must be called on every render (rules of hooks), so it
  // sits before the `if (!room) return …` short-circuit. uploadFiles closes
  // over `id` and `refresh`, both of which are valid even when room is null
  // (the dropzone is also disabled in that case via `enabled`).
  const uploadFiles = async (files: File[]) => {
    if (!id || files.length === 0) return;
    setError("");
    const yamlFiles = files.filter((f) => /\.ya?ml$/i.test(f.name));
    const skipped = files.length - yamlFiles.length;
    if (yamlFiles.length === 0) {
      setError(skipped > 0 ? "No .yaml/.yml files in the dropped set" : "No files to upload");
      return;
    }
    try {
      for (const file of yamlFiles) {
        await uploadYaml(id, file);
      }
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  };

  const dropZone = useFileDropZone({
    enabled: room?.status === "open",
    onFiles: uploadFiles,
  });

  if (error) return <p className="error">{error}</p>;
  if (!room) return <p className="loading">Loading...</p>;

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    await uploadFiles(files);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleClose = async () => {
    if (!id) return;
    setActionLoading("closing");
    await closeRoom(id);
    refresh();
    setActionLoading("");
  };

  const handleReopen = async () => {
    if (!id) return;
    setActionLoading("reopening");
    try {
      await reopenRoom(id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reopen room");
    }
    setActionLoading("");
  };

  const handleGenerate = async () => {
    if (!id) return;
    setActionLoading("generating");
    setGenLog("");
    setError("");
    try {
      const result = await generateRoom(id);
      // Seed the polling effect by fetching the job we just enqueued (or the
      // already-running one the API pointed at).
      const fresh = await getGenerationJob(id, result.job_id);
      setGenJob(fresh);
      if (fresh.log) setGenLog(fresh.log);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      refresh();
      setActionLoading("");
    }
  };

  const handleLaunch = async () => {
    if (!id) return;
    setActionLoading("launching");
    try {
      await launchRoom(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Launch failed");
    }
    refresh();
    setActionLoading("");
  };

  const handleTestGenerate = async () => {
    if (!id) return;
    setActionLoading("testing");
    setGenLog("");
    setError("");
    try {
      const result = await testGenerateRoom(id);
      if (result.log) setGenLog(result.log);
      if (!result.success) {
        setError(result.error ?? "Test generation failed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Test generation failed");
    }
    setActionLoading("");
  };

  const handleRemoveYaml = async (yamlId: number) => {
    if (!id) return;
    await removeYaml(id, yamlId);
    refresh();
  };

  // FEAT-25: bulk-download every pinned APWorld file. Backend returns 400
  // when nothing's pinned (cleaner than handing the host an empty zip);
  // we fetch via blob so we can read the JSON error and toast it instead
  // of letting the browser dump it on a navigated tab.
  const handleDownloadAllAPWorlds = async () => {
    if (!id) return;
    setError("");
    try {
      const resp = await fetch(`/api/rooms/${id}/apworlds/download-all`);
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.error ?? `Download failed (${resp.status})`);
      }
      const blob = await resp.blob();
      const cd = resp.headers.get("Content-Disposition") ?? "";
      const match = /filename="?([^";]+)"?/i.exec(cd);
      const fname = match?.[1] ?? "apworlds.zip";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "APWorld download failed");
    }
  };

  const handleStopServer = async () => {
    if (!id) return;
    setActionLoading("stopping");
    try {
      await stopRoom(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stop failed");
    }
    refresh();
    setActionLoading("");
  };

  const handleDelete = async () => {
    if (!id || !confirm("Delete this room? This cannot be undone.")) return;
    await deleteRoom(id);
    navigate("/rooms");
  };

  const yamls = room.yamls ?? [];
  const allValid = yamls.length > 0 && yamls.every(
    (y) => y.validation_status === "validated" || y.validation_status === "manually_validated"
  );

  // allValid intentionally uses the full yamls list - even when the table is
  // filtered, generation requires every uploaded YAML to be valid.
  const displayedYamls = filterAndSortYamls(yamls, yamlSearch, yamlSort);
  const toggleSort = (key: YamlSortKey) => setYamlSort((cur) => nextSort(cur, key));

  return (
    <div {...dropZone.handlers} style={{ position: "relative", minHeight: "100vh" }}>
      {dropZone.isDragging && <DropOverlay label="Drop YAMLs anywhere to upload" />}
      {viewingYamlId !== null && (
        <YamlModal
          roomId={room.id}
          yamlId={viewingYamlId}
          /* Host has admin-level control over every YAML in their room
             (open or closed; generated/playing rooms have a locked seed
             so editing would invalidate it - mirrored in the backend
             route's status check). The route is auth-gated by the
             blueprint's _enforce_room_ownership middleware. */
          canEdit={room.status === "open" || room.status === "closed"}
          update={(content) => updateRoomYaml(room.id, viewingYamlId, content)}
          onClose={() => setViewingYamlId(null)}
          onUpdated={async () => {
            setViewingYamlId(null);
            await refresh();
          }}
        />
      )}
      <Link to="/rooms" className="back-link">&larr; Back to rooms</Link>

      <EditableRoomHeader
        room={room}
        onUpdate={refresh}
        onDelete={handleDelete}
        onOpenSettings={() => setShowSettings(true)}
        shareControl={<SharePublicRoomButton roomId={room.id} />}
      />

      {showSettings && (
        <RoomSettingsModal
          room={room}
          onClose={() => setShowSettings(false)}
          onUpdate={refresh}
        />
      )}

      {error && <p className="error">{error}</p>}

      {/* Live progress moved above Submitted YAMLs (2026-05-04) to match
          the public room layout, which Stef preferred — the live grid is
          the most engaging surface when there is anything to look at, and
          the YAML list works fine collapsed underneath when the host is
          watching a run. Items tab is local-only since the external
          tracker doesn't expose item-level data. */}
      {id && (room.status === "playing" || (room.status === "generated" && room.seed) || room.tracker_url) && (
        <details className="collapsible-section" open>
          <summary>
            <h2 style={{ marginTop: 0 }}>Live progress</h2>
          </summary>
          <div className="accordion-body">
            {room.seed && (
              <div className="market-tabs" style={{ marginTop: "0.25rem" }}>
                <button
                  className={`btn btn-sm${trackerTab === "progress" ? " btn-primary" : ""}`}
                  onClick={() => setTrackerTab("progress")}
                >Progress</button>
                <button
                  className={`btn btn-sm${trackerTab === "items" ? " btn-primary" : ""}`}
                  onClick={() => setTrackerTab("items")}
                >Items</button>
              </div>
            )}
            {(trackerTab === "items" && room.seed)
              ? <ItemTracker roomId={id} />
              : <LiveTracker
                  roomId={id}
                  viewerSlotNames={
                    user
                      ? yamls
                          .filter((y) => y.submitter_user_id != null && y.submitter_user_id === user.id)
                          .map((y) => y.player_name)
                      : []
                  }
                />}
          </div>
        </details>
      )}

      {/* Submitted YAMLs (Players) - wrapped in <details> so hosts can
          collapse the table when they want the live tracker / actions to
          dominate. The drag-and-drop hint and search bar live inside the
          accordion body so they only render when the section is open. */}
      <details className="collapsible-section" open>
        <summary>
          <h2 style={{ marginTop: 0 }}>Submitted YAMLs ({yamls.length})</h2>
        </summary>
        <div className="accordion-body">
        <div className="yaml-list-header">
          {room.status === "open" && (
            <span className="muted" style={{ fontSize: "0.85em" }}>
              drop YAMLs anywhere on this page
            </span>
          )}
          {yamls.length > 0 && (
            <div className="yaml-toolbar">
              <input
                type="search"
                value={yamlSearch}
                onChange={(e) => setYamlSearch(e.target.value)}
                placeholder="Search player, game, or file…"
                aria-label="Search YAMLs"
                className="yaml-search"
              />
              {yamlSearch.trim() && (
                <span className="muted yaml-count">
                  {displayedYamls.length} of {yamls.length}
                </span>
              )}
            </div>
          )}
        </div>
      {yamls.length === 0 ? (
        <p className="muted">
          {room.status === "open"
            ? "No YAMLs uploaded yet - drag .yaml files anywhere on this page, or use the buttons below."
            : "No YAMLs uploaded yet."}
        </p>
      ) : displayedYamls.length === 0 ? (
        <p className="muted">No matches for &ldquo;{yamlSearch}&rdquo;.</p>
      ) : (
        <div className="table-wrapper">
          <table className="game-table">
            <thead>
              <tr>
                <th aria-sort={ariaSortValue(yamlSort, "player")}>
                  <button type="button" className="sort-th" onClick={() => toggleSort("player")}>
                    Player{sortIndicator(yamlSort, "player")}
                  </button>
                </th>
                <th aria-sort={ariaSortValue(yamlSort, "game")}>
                  <button type="button" className="sort-th" onClick={() => toggleSort("game")}>
                    Game{sortIndicator(yamlSort, "game")}
                  </button>
                </th>
                <th aria-sort={ariaSortValue(yamlSort, "file")}>
                  <button type="button" className="sort-th" onClick={() => toggleSort("file")}>
                    File{sortIndicator(yamlSort, "file")}
                  </button>
                </th>
                <th aria-sort={ariaSortValue(yamlSort, "status")}>
                  <button type="button" className="sort-th" onClick={() => toggleSort("status")}>
                    Status{sortIndicator(yamlSort, "status")}
                  </button>
                </th>
                <th aria-sort={ariaSortValue(yamlSort, "submitter")}>
                  <button type="button" className="sort-th" onClick={() => toggleSort("submitter")}>
                    Uploader{sortIndicator(yamlSort, "submitter")}
                  </button>
                </th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {displayedYamls.map((y) => (
                <tr key={y.id}>
                  <td>{y.player_name}</td>
                  <td>
                    <GameCell
                      game={y.game}
                      lookup={apworldLookup}
                      apworldVersions={y.apworld_versions}
                      pinByApworld={pinByApworld}
                    />
                  </td>
                  <td className="muted">{cleanYamlFilename(y.filename, y.player_name, y.game)}</td>
                  <td><ValidationBadge status={y.validation_status} error={y.validation_error} /></td>
                  <td className="muted">{y.submitter_username ?? "-"}</td>
                  <td className="yaml-row-actions-cell">
                    <div className="yaml-row-actions">
                      <button
                        type="button"
                        className="btn btn-sm"
                        onClick={() => setViewingYamlId(y.id)}
                      >
                        View
                      </button>
                      <a href={`/api/rooms/${room.id}/yamls/${y.id}/download`} className="btn btn-sm" download>
                        Download
                      </a>
                      {(y.validation_status === "failed" || y.validation_status === "unsupported" || y.validation_status === "unknown") && (
                        <button
                          type="button"
                          className="btn btn-sm"
                          title="Trust this YAML and let it through generation despite the validator"
                          onClick={async () => {
                            try {
                              await setYamlValidation(room.id, y.id, "manually_validated");
                              refresh();
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "Override failed");
                            }
                          }}
                        >
                          Mark valid
                        </button>
                      )}
                      {y.validation_status === "manually_validated" && (
                        <button
                          type="button"
                          className="btn btn-sm"
                          title="Re-run validation on this YAML"
                          onClick={async () => {
                            try {
                              await setYamlValidation(room.id, y.id, "unknown");
                              refresh();
                            } catch (e) {
                              setError(e instanceof Error ? e.message : "Reset failed");
                            }
                          }}
                        >
                          Unset override
                        </button>
                      )}
                      {room.status === "open" && (
                        <button type="button" className="btn btn-sm btn-danger" onClick={() => handleRemoveYaml(y.id)}>
                          Remove
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
        </div>
      </details>

      {/* Actions */}
      <div className="room-actions">
        {room.status === "open" && (
          <>
            {/* Native <label>-wrap pattern: BUG-02 (Chrome double-fires the
                file picker when .click() is called from an outer click handler).
                Letting the label handle it natively fires the picker exactly once. */}
            <label className="btn btn-primary" style={{ cursor: "pointer" }}>
              Upload YAML
              <input
                ref={fileRef}
                type="file"
                accept=".yaml,.yml"
                multiple
                onChange={handleUpload}
                style={{ position: "absolute", width: 1, height: 1, opacity: 0, pointerEvents: "none" }}
              />
            </label>
            <button className="btn btn-primary" onClick={() => setShowEditor(true)}>
              Create YAML
            </button>
            {generationOn && yamls.length > 0 && (
              <button
                className="btn"
                onClick={handleTestGenerate}
                disabled={!allValid || actionLoading === "testing"}
                title={!allValid ? "All YAMLs must be valid to test generation" : undefined}
              >
                {actionLoading === "testing" ? "Testing..." : "Test Generation"}
              </button>
            )}
            <button
              className="btn"
              onClick={handleClose}
              disabled={yamls.length === 0 || actionLoading === "closing"}
              title={yamls.length === 0 ? "Upload at least one YAML before closing" : undefined}
            >
              {actionLoading === "closing" ? "Closing..." : "Close Room"}
            </button>
          </>
        )}

        {room.status === "closed" && (() => {
          const inFlight = genJob?.status === "queued" || genJob?.status === "running";
          return (
            <button
              className="btn"
              onClick={handleReopen}
              disabled={inFlight || actionLoading === "reopening" || actionLoading === "generating"}
              title={inFlight ? "Generation in progress - wait for it to finish or fail" : "Reopen the room to add more YAMLs"}
            >
              {actionLoading === "reopening" ? "Reopening..." : "Reopen Room"}
            </button>
          );
        })()}

        {generationOn && (room.status === "closed" || room.status === "generating") && (() => {
          const inFlight = genJob?.status === "queued" || genJob?.status === "running";
          const label = inFlight
            ? (genJob?.status === "queued" ? "Queued..." : "Generating...")
            : actionLoading === "generating"
              ? "Generating..."
              : "Generate Game";
          return (
            <button
              className="btn btn-primary"
              onClick={handleGenerate}
              disabled={!allValid || inFlight || actionLoading === "generating"}
              title={!allValid ? "All YAMLs must be valid to generate" : undefined}
            >
              {label}
            </button>
          );
        })()}

        {/* Server-side generation disabled hint dropped — the absence of a
            Generate button + the presence of "Download all YAMLs" already
            tells hosts what to do, and a sentence in the action bar adds
            noise. Restore behind a config flag if hosts get confused. */}

        {generationOn && room.status === "generated" && (
          <button
            className="btn btn-primary"
            onClick={handleLaunch}
            disabled={actionLoading === "launching"}
          >
            {actionLoading === "launching" ? "Launching..." : "Launch Server"}
          </button>
        )}

        {generationOn && room.status === "playing" && (
          <button
            className="btn btn-danger"
            onClick={handleStopServer}
            disabled={actionLoading === "stopping"}
          >
            {actionLoading === "stopping" ? "Stopping..." : "Stop Server"}
          </button>
        )}

        {yamls.length > 0 && (
          <a
            href={`/api/rooms/${room.id}/yamls/download-all`}
            className="btn"
            download
          >
            Download all YAMLs
          </a>
        )}

        {yamls.length > 0 && (
          <button
            type="button"
            className="btn"
            onClick={handleDownloadAllAPWorlds}
            title="Bundle every APWorld pinned for this room into a zip (skips built-in worlds and games not in the index)"
          >
            Download all APWorlds
          </button>
        )}

        {room.seed && (
          <>
            <ShareGame seed={room.seed} buttonLabel="Share" buttonClassName="btn btn-primary" />
            <Link to={`/games/${room.seed}`} className="btn">View Game Details</Link>
            <a href={`/api/rooms/${room.id}/download`} className="btn" download>
              Download Game
            </a>
            <button
              className="btn"
              disabled={spoilerLoading}
              onClick={async () => {
                if (spoilerLog !== null) { setSpoilerLog(null); return; }
                setSpoilerLoading(true);
                try {
                  const data = await getRoomSpoiler(id!);
                  setSpoilerLog(data.content);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Could not load spoiler log");
                }
                setSpoilerLoading(false);
              }}
            >
              {spoilerLoading ? "Loading..." : spoilerLog !== null ? "Hide Spoiler" : "Spoiler Log"}
            </button>
          </>
        )}
      </div>

      {/* YAML Editor */}
      {showEditor && id && (
        <YamlEditor
          roomId={id}
          onComplete={() => { setShowEditor(false); refresh(); }}
          onCancel={() => setShowEditor(false)}
        />
      )}

      {/* Patch Downloads */}
      {patches.length > 0 && (
        <div className="detail-section">
          <h3>Patch Files</h3>
          <ul>
            {patches.map((p) => (
              <li key={p}>
                <a href={`/api/rooms/${room.id}/patches/${p}`} download>{p}</a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Spoiler Log */}
      {spoilerLog !== null && (
        <details className="detail-section gen-log-details" open>
          <summary className="gen-log-summary">Spoiler Log</summary>
          <pre className="gen-log">{spoilerLog}</pre>
        </details>
      )}

      {/* Generation Log (auto-expand on failure) */}
      {genLog && (
        <details className="detail-section gen-log-details" open={!!error || room.status === "closed"}>
          <summary className="gen-log-summary">Generation Log</summary>
          <pre className="gen-log">{genLog}</pre>
        </details>
      )}

      {/* Room activity log: server-side audit trail of host-level events
          (room created, YAMLs uploaded/claimed/released/deleted, settings
          changed, etc.). Different from the Live activity panel inside
          LiveTracker, which streams in-game PrintJSON events. Collapsed
          by default — useful for forensics when something goes wrong but
          rarely needed in daily ops. */}
      {room.activity && room.activity.length > 0 && (
        <details className="collapsible-section detail-section">
          <summary>
            <h3 style={{ marginTop: 0 }}>Room activity log ({room.activity.length})</h3>
          </summary>
          <div className="accordion-body">
            <div className="activity-feed">
              {room.activity.map((a) => (
                <div key={a.id} className="activity-item">
                  <span className={`activity-dot activity-${a.event_type}`} />
                  <span className="activity-message">{a.message}</span>
                  <span className="activity-time">{new Date(a.created_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>
        </details>
      )}
    </div>
  );
}
