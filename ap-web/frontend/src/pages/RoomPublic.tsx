import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  claimYaml,
  deletePublicYaml,
  getPublicRoom,
  getPublicRoomAPWorlds,
  releaseYaml,
  submitYamlToRoom,
  submitYamlContentToRoom,
  type PublicRoom,
  type PublicRoomYaml,
  type RoomAPWorldEntry,
  type ValidationStatus,
} from "../api";
import { useAuth } from "../context/AuthContext";
import { useFileDropZone } from "../lib/useFileDropZone";
import { usePageTitle } from "../lib/usePageTitle";
import { formatDeadlineAbsolute, formatDeadlineCountdown } from "../lib/roomDeadline";
import {
  cleanYamlFilename,
  filterAndSortYamls,
  nextSort,
  sortIndicator,
  ariaSortValue,
  type YamlSort,
  type YamlSortKey,
} from "../lib/yamlTable";
import DropOverlay from "../components/DropOverlay";
import YamlModal from "../components/YamlModal";
import CopyButton from "../components/CopyButton";
import DropZone from "../components/DropZone";
import LiveTracker from "../components/LiveTracker";
import GameCell from "../components/GameCell";
import { useAPWorldLookup } from "../lib/apworldLookup";

/**
 * Public room landing page. No auth required.
 *
 * The Bananium-shaped page: a host shares /r/<roomId> with their players,
 * players land here, see what's been submitted so far, and drop their own
 * YAML. Once the host generates and a seed is assigned, the page links
 * through to /play/<seed> for connection details.
 *
 * Auth-gated host actions (closing the room, generating, server controls)
 * stay on /rooms/<id>; this page is read + submit only.
 */

function StatusBadge({ status }: { status: string }) {
  // "open" is the call-to-action state - paint it loud (warm accent), not
  // muted. Anything terminal/transient gets a calmer treatment.
  const cls =
    status === "open" ? "badge badge-active" :
    status === "playing" ? "badge badge-done" :
    status === "generating" ? "badge badge-progress" :
    status === "generated" ? "badge badge-save" :
    "badge";
  return <span className={cls}>{status}</span>;
}

function ValidationBadge({ y }: { y: PublicRoomYaml }) {
  switch (y.validation_status as ValidationStatus) {
    case "validated":
      return <span className="badge badge-done">Validated</span>;
    case "manually_validated":
      return <span className="badge badge-trusted" title="Marked valid by host">Host-trusted</span>;
    case "unsupported":
      return <span className="badge badge-warn" title="apworld for this game isn't installed">Unsupported</span>;
    case "failed":
      return <span className="badge badge-error" title={y.validation_error ?? ""}>Failed</span>;
    case "unknown":
    default:
      return <span className="badge badge-pending">Pending</span>;
  }
}

interface SubmitState {
  busy: boolean;
  busyLabel: string;
  error: string;
  success: string | null;
}

const IDLE_SUBMIT_STATE: SubmitState = { busy: false, busyLabel: "", error: "", success: null };

function PageBanner({ room }: { room: PublicRoom }) {
  // External server connection details previously got a hero block here.
  // The LiveTracker now surfaces the same `host:port` in its connection bar
  // alongside live status, so duplicating it as a banner just adds noise.
  // Keep this function for the seed / playing / generating flows below.
  if (room.seed && room.status === "playing") {
    return (
      <div className="play-banner play-banner-ok public-section">
        <strong>Game is live.</strong>{" "}
        <Link to={`/play/${room.seed}`}>See connection details &rarr;</Link>
      </div>
    );
  }
  if (room.status === "generating") {
    return (
      <div className="play-banner play-banner-info public-section">
        <strong>Generation in progress.</strong> The host is putting the multiworld together - this page will update.
      </div>
    );
  }
  if (room.seed && room.status === "generated") {
    return (
      <div className="play-banner play-banner-info public-section">
        <strong>Multiworld is ready.</strong>{" "}
        <Link to={`/play/${room.seed}`}>Get your patch &rarr;</Link>
      </div>
    );
  }
  if (room.status === "closed") {
    // No banner for plain "closed" — the room status badge near the title
    // already conveys "submissions closed" and a top-bar message implying
    // the host is mid-generation can be misleading when generation is off
    // on this deployment. Generated / playing / generating still get
    // banners since those states carry actionable next steps.
    return null;
  }
  return null;
}

function SubmissionForm({
  room,
  uploadFiles,
  state,
  setState,
  onSubmitted,
}: {
  room: PublicRoom;
  uploadFiles: (files: File[]) => Promise<void>;
  state: SubmitState;
  setState: React.Dispatch<React.SetStateAction<SubmitState>>;
  onSubmitted: () => void;
}) {
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasted, setPasted] = useState("");

  if (room.status !== "open") return null;

  const handlePaste = async () => {
    if (!pasted.trim()) return;
    setState({ busy: true, busyLabel: "Submitting pasted YAML…", error: "", success: null });
    try {
      const r = await submitYamlContentToRoom(room.id, pasted);
      setState({
        busy: false,
        busyLabel: "",
        error: "",
        success: `Submitted ${r.player_name} (${r.game}) - ${r.validation_status}`,
      });
      setPasted("");
      setPasteOpen(false);
      onSubmitted();
    } catch (e) {
      setState({
        busy: false,
        busyLabel: "",
        error: e instanceof Error ? e.message : "Submission failed",
        success: null,
      });
    }
  };

  return (
    <section className="play-card public-section">
      <h2>Submit your YAML</h2>
      <p className="play-hint" style={{ marginBottom: "0.85rem" }}>
        Drop <code>.yaml</code> files anywhere on this page, click below to browse,
        or paste the contents directly.
      </p>

      <DropZone
        onFiles={uploadFiles}
        busy={state.busy}
        busyLabel={state.busyLabel || "Submitting…"}
        headline="Drop YAML files here"
        hint="or click to browse - drag from anywhere on the page also works"
      />

      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.85rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => setPasteOpen((v) => !v)}
          disabled={state.busy}
        >
          {pasteOpen ? "Hide paste editor" : "Paste YAML instead"}
        </button>
      </div>

      {pasteOpen && (
        <div style={{ marginTop: "0.75rem" }}>
          <textarea
            rows={10}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
            placeholder="Paste your YAML here…"
            style={{
              width: "100%",
              fontFamily: "var(--font-mono)",
              fontSize: "0.85rem",
              background: "var(--bg)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "0.6rem 0.75rem",
              resize: "vertical",
            }}
          />
          <button
            className="btn btn-primary"
            onClick={handlePaste}
            disabled={state.busy || !pasted.trim()}
            style={{ marginTop: "0.5rem" }}
          >
            {state.busy ? "Submitting…" : "Submit pasted YAML"}
          </button>
        </div>
      )}
      {state.error && <p className="error" style={{ marginTop: "0.85rem", textAlign: "left", padding: "0.5rem 0" }}>{state.error}</p>}
      {state.success && (
        <p className="play-hint" style={{ marginTop: "0.85rem", color: "var(--green)" }}>
          ✓ {state.success}
        </p>
      )}
    </section>
  );
}

function DiscordLoginGate({ roomId }: { roomId: string }) {
  const { login, user } = useAuth();
  return (
    <section className="play-card public-section">
      <h2>Login required</h2>
      <p className="play-hint" style={{ marginBottom: "0.85rem" }}>
        The room owner has set this room to <strong style={{ color: "var(--text-h)" }}>require Discord login</strong> before
        submitting a YAML. Sign in with Discord - the room owner will see your Discord identity next to your submission.
      </p>
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => login(`/r/${roomId}`)}
        disabled={!!user}
      >
        Login with Discord
      </button>
    </section>
  );
}

function RoomPublic() {
  const { id = "" } = useParams<{ id: string }>();
  const { user } = useAuth();
  const apworldLookup = useAPWorldLookup();
  const [room, setRoom] = useState<PublicRoom | null>(null);
  // FEAT-21: per-room APWorld pins surfaced to players as install links.
  // Only games the host has pinned a version for are returned (the public
  // API filters out unpinned games; see api/public.py).
  const [apworlds, setApworlds] = useState<RoomAPWorldEntry[]>([]);
  // FEAT-28 v2: derived pin map for the per-YAML Version column. Built
  // from the same apworlds payload (saves a separate fetch).
  const pinByApworld = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of apworlds) {
      if (e.apworld_name && e.selected_version) {
        m.set(e.apworld_name, e.selected_version);
      }
    }
    return m;
  }, [apworlds]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitState, setSubmitState] = useState<SubmitState>(IDLE_SUBMIT_STATE);
  // Single modal state - open YAMLs by id, with an optional initialTab
  // so the Edit button lands directly on the Edit pane while the View
  // button lands on read-only View. Same modal serves both.
  const [openYaml, setOpenYaml] = useState<{ id: number; tab: "view" | "edit" } | null>(null);
  const [deletingYamlId, setDeletingYamlId] = useState<number | null>(null);
  // FEAT-20: tracks which row's claim/release is in flight, so the button
  // can render busy state without blocking other rows. Also surfaces server
  // errors (race-loss, cap-exceeded, etc.) inline next to the button.
  const [claimingYamlId, setClaimingYamlId] = useState<number | null>(null);
  const [claimError, setClaimError] = useState<{ id: number; msg: string } | null>(null);
  // Toast surfacing for the FEAT-18 update flow. Goes back to null on the
  // next refresh tick so the message doesn't linger across actions.
  const [updateToast, setUpdateToast] = useState<string | null>(null);
  const [yamlSearch, setYamlSearch] = useState("");
  const [yamlSort, setYamlSort] = useState<YamlSort | null>(null);
  const toggleSort = (key: YamlSortKey) => setYamlSort((cur) => nextSort(cur, key));

  usePageTitle(room?.name);

  const refreshRef = useRef<() => Promise<void>>(async () => {});

  const uploadFiles = useCallback(async (files: File[]) => {
    if (!id) return;
    const yamlFiles = files.filter((f) => /\.ya?ml$/i.test(f.name));
    const skipped = files.length - yamlFiles.length;
    if (yamlFiles.length === 0) {
      setSubmitState({
        busy: false,
        busyLabel: "",
        error: skipped > 0 ? "Only .yaml/.yml files are accepted" : "No files to submit",
        success: null,
      });
      return;
    }
    const total = yamlFiles.length;
    const results: string[] = [];
    try {
      for (let i = 0; i < yamlFiles.length; i++) {
        const file = yamlFiles[i];
        setSubmitState({
          busy: true,
          busyLabel: total > 1 ? `Submitting ${i + 1}/${total}…` : `Submitting ${file.name}…`,
          error: "",
          success: null,
        });
        const r = await submitYamlToRoom(id, file);
        results.push(`${r.player_name} (${r.game}) - ${r.validation_status}`);
      }
      setSubmitState({
        busy: false,
        busyLabel: "",
        error: "",
        success: `Submitted ${results.join(", ")}`,
      });
      await refreshRef.current();
    } catch (e) {
      setSubmitState({
        busy: false,
        busyLabel: "",
        error: e instanceof Error ? e.message : "Submission failed",
        success: results.length > 0 ? `Submitted before error: ${results.join(", ")}` : null,
      });
    }
  }, [id]);

  const dropZone = useFileDropZone({
    // Disabled while the login gate is showing - a logged-out drag-drop would
    // hit the backend and bounce with a 401 anyway, but disabling client-side
    // saves the round trip and keeps the gate honest.
    enabled: room?.status === "open" && !(room?.require_discord_login && !user),
    onFiles: uploadFiles,
  });

  const refresh = async () => {
    if (!id) return;
    try {
      const r = await getPublicRoom(id);
      setRoom(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Room not found");
    } finally {
      setLoading(false);
    }
    // APWorld pins are independent of room status changes - swallow errors
    // (the panel just stays empty rather than blowing up the whole page).
    try {
      const aw = await getPublicRoomAPWorlds(id);
      setApworlds(aw);
    } catch {
      // index unavailable / 5xx - leave the previous panel state alone
    }
  };

  refreshRef.current = refresh;

  // 5s polling. Initial fetch fires on mount; the interval is paused while
  // any modal is open. The cascading parent re-render disrupts focus and
  // selection inside the modal (pleb 2026-05-03 reported "edits stop every
  // few seconds and i have to click back on screen"; Riannehx reported
  // visual flickering across Opera/Firefox/Chrome). The user is actively
  // interacting with the modal, so passive background updates aren't worth
  // the disruption - onUpdated resyncs after a save anyway.
  const modalOpen = openYaml !== null;
  useEffect(() => {
    let cancelled = false;
    refresh();
    return () => { cancelled = true; void cancelled; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  useEffect(() => {
    if (modalOpen) return;
    let cancelled = false;
    const interval = setInterval(() => {
      if (!cancelled) refresh();
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modalOpen]);

  if (loading && !room) return <p className="loading">Loading room…</p>;
  if (error || !room) {
    return (
      <div>
        <h1>Room not found</h1>
        <p className="play-hint">
          The room <code>{id}</code> doesn't exist on this server. Double-check the link
          your host shared with you.
        </p>
      </div>
    );
  }

  const yamls = room.yamls;
  const displayedYamls = filterAndSortYamls(yamls, yamlSearch, yamlSort);
  const shareUrl = typeof window !== "undefined"
    ? `${window.location.origin}/r/${room.id}`
    : `/r/${room.id}`;

  return (
    <div {...dropZone.handlers} style={{ position: "relative" }}>
      {dropZone.isDragging && <DropOverlay label="Drop YAMLs anywhere to submit" />}
      {openYaml !== null && id && (() => {
        const targetYaml = yamls.find((y) => y.id === openYaml.id);
        // Prefer numeric id match (reliable across rename + claim flows);
        // fall back to discord_username for backwards compat with older
        // payloads that might not include submitter_user_id yet.
        const isMine = !!user && !!targetYaml && (
          (targetYaml.submitter_user_id != null && targetYaml.submitter_user_id === user.id) ||
          (!!targetYaml.submitter_username && targetYaml.submitter_username === user.discord_username)
        );
        const canEdit = isMine && room?.status === "open";
        return (
          <YamlModal
            roomId={id}
            yamlId={openYaml.id}
            canEdit={canEdit}
            initialTab={openYaml.tab}
            onClose={() => setOpenYaml(null)}
            onUpdated={async (result) => {
              setOpenYaml(null);
              const fragment = result.renamed && result.previous_player_name
                ? `renamed ${result.previous_player_name} → ${result.player_name}`
                : `updated ${result.player_name}`;
              const validity = result.validation_status === "validated"
                ? "validated"
                : result.validation_status === "failed"
                  ? `failed: ${result.validation_error || "validation error"}`
                  : result.validation_status;
              setUpdateToast(`YAML ${fragment} (${validity}).`);
              await refresh();
            }}
          />
        );
      })()}

      <header style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", marginBottom: "0.5rem" }}>
          <StatusBadge status={room.status} />
          <CopyButton value={shareUrl} label="Copy room link" copiedLabel="Link copied!" />
        </div>
        <h1 style={{ marginBottom: "0.5rem" }}>{room.name}</h1>
        <p className="play-hint" style={{ margin: 0 }}>
          Hosted by <strong style={{ color: "var(--text-h)" }}>{room.host_name}</strong>
          {room.race_mode && <> · race mode</>}
          {room.claim_mode && <> · <strong style={{ color: "var(--text-h)" }}>claim mode</strong></>}
          {" · "}
          {room.player_count} {room.player_count === 1 ? "player" : "players"}
          {room.max_players > 0 && <> / cap {room.max_players}</>}
          {room.max_yamls_per_user > 0 && <> · {room.max_yamls_per_user} per Discord user</>}
        </p>
        {room.claim_mode && (
          <p className="play-hint" style={{ margin: "0.35rem 0 0", fontStyle: "italic" }}>
            The host pre-loaded the YAMLs below. Pick a slot, claim it, optionally tweak it.
          </p>
        )}
        {room.submit_deadline && room.status === "open" && (
          <p className="play-hint" style={{ margin: "0.35rem 0 0" }}>
            <strong style={{ color: "var(--text-h)" }}>Submissions close</strong>{" "}
            <span title={formatDeadlineAbsolute(room.submit_deadline)}>
              {formatDeadlineAbsolute(room.submit_deadline)} ({formatDeadlineCountdown(room.submit_deadline)})
            </span>
          </p>
        )}
        {room.description && (
          <p className="muted" style={{ marginTop: "0.5rem" }}>{room.description}</p>
        )}
      </header>

      <PageBanner room={room} />

      {updateToast && (
        <div className="public-toast" role="status">
          {updateToast}
          <button
            type="button"
            className="btn btn-sm public-toast-dismiss"
            onClick={() => setUpdateToast(null)}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {room.tracker_url && (
        <details className="play-card public-section collapsible-section" open>
          <summary>
            <h2 style={{ marginTop: 0 }}>Live progress</h2>
          </summary>
          <div className="accordion-body">
            <LiveTracker
              roomId={room.id}
              publicMode
              /* "My slots" matches the tracker grid against the player_names
                 of YAMLs the viewer submitted (FEAT-13 anonymous viewers
                 don't get submitter ids back, so the filter just stays
                 hidden for them — Set is empty). */
              viewerSlotNames={
                user
                  ? yamls
                      .filter(
                        (y) =>
                          (y.submitter_user_id != null && y.submitter_user_id === user.id) ||
                          (!!y.submitter_username && y.submitter_username === user.discord_username),
                      )
                      .map((y) => y.player_name)
                  : []
              }
            />
          </div>
        </details>
      )}

      {/* The full-width "APWorlds you need to install" panel was removed
          2026-05-03 — it dominated the player-facing room page and
          duplicated info already surfaced inline as version pills next
          to each game in the YAML table below. Players who want a
          specific .apworld can click the game name in the table to
          land on /apworlds?search=<game>. The `apworlds` fetch above
          stays - we still need it to build `pinByApworld` for the
          inline pill rendering in the YAML table. */}

      <details className="play-card public-section collapsible-section" open>
        <summary>
          <h2 style={{ marginTop: 0 }}>Submitted YAMLs ({yamls.length})</h2>
        </summary>
        <div className="accordion-body">
        {yamls.length > 0 && (
          <div className="yaml-list-header">
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
          </div>
        )}
        {yamls.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-art" aria-hidden="true">🥧</span>
            <span className="empty-state-title">An empty pie tin.</span>
            <span>
              {room.status !== "open"
                ? "No YAMLs were submitted to this room."
                : room.claim_mode
                  ? "The host hasn't pre-loaded any slots yet - check back soon."
                  : "Be the first to add a slice - drop a YAML below."}
            </span>
          </div>
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
                  {!!user && (
                    <th aria-sort={ariaSortValue(yamlSort, "submitter")}>
                      <button type="button" className="sort-th" onClick={() => toggleSort("submitter")}>
                        {room.claim_mode ? "Claimed by" : "Uploader"}{sortIndicator(yamlSort, "submitter")}
                      </button>
                    </th>
                  )}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {displayedYamls.map((y) => {
                  // FEAT-20 ownership check: prefer numeric id match (works
                  // for both "I uploaded this" and "I claimed this slot in
                  // claim-mode"). Username equality fallback is kept for
                  // payloads that don't yet carry submitter_user_id.
                  const isMine = !!user && (
                    (y.submitter_user_id != null && y.submitter_user_id === user.id) ||
                    (!!y.submitter_username && y.submitter_username === user.discord_username)
                  );
                  const unclaimed = room.claim_mode && y.submitter_user_id == null;
                  const claimedByOther = room.claim_mode && y.submitter_user_id != null && !isMine;
                  return (
                  <tr key={y.id}>
                    <td><strong>{y.player_name}</strong></td>
                    <td>
                      <GameCell
                        game={y.game}
                        lookup={apworldLookup}
                        apworldVersions={y.apworld_versions}
                        pinByApworld={pinByApworld}
                      />
                    </td>
                    <td className="muted">{cleanYamlFilename(y.filename, y.player_name, y.game)}</td>
                    <td>
                      <ValidationBadge y={y} />
                      {unclaimed && (
                        <span className="badge badge-pending" style={{ marginLeft: "0.35rem" }}>
                          Unclaimed
                        </span>
                      )}
                    </td>
                    {!!user && (
                      <td className="muted">
                        {y.submitter_username ?? (room.claim_mode ? "-" : "-")}
                      </td>
                    )}
                    <td className="yaml-row-actions-cell">
                      <div className="yaml-row-actions">
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => setOpenYaml({ id: y.id, tab: "view" })}
                        >
                          View
                        </button>
                        <a
                          href={`/api/public/rooms/${room.id}/yamls/${y.id}/download`}
                          className="btn btn-sm"
                          download
                        >
                          Download
                        </a>
                        {/* FEAT-20: Claim / Release. Only relevant in claim_mode.
                            Login required - anonymous viewers see View+Download only. */}
                        {unclaimed && room.status === "open" && user && (
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={claimingYamlId === y.id}
                            title="Take this slot. You'll be able to edit the YAML afterwards if you want to tweak it."
                            onClick={async () => {
                              setClaimingYamlId(y.id);
                              setClaimError(null);
                              try {
                                await claimYaml(room.id, y.id);
                                await refresh();
                              } catch (e) {
                                setClaimError({ id: y.id, msg: e instanceof Error ? e.message : "Claim failed" });
                              } finally {
                                setClaimingYamlId(null);
                              }
                            }}
                          >
                            {claimingYamlId === y.id ? "Claiming…" : "Claim"}
                          </button>
                        )}
                        {unclaimed && room.status === "open" && !user && (
                          <a className="btn btn-sm btn-primary" href={`/api/auth/login?next=/r/${room.id}`}>
                            Login to claim
                          </a>
                        )}
                        {room.claim_mode && isMine && room.status === "open" && (
                          <button
                            type="button"
                            className="btn btn-sm"
                            disabled={claimingYamlId === y.id}
                            title="Drop this slot back into the unclaimed pool."
                            onClick={async () => {
                              if (!confirm(`Release your claim on ${y.player_name}?`)) return;
                              setClaimingYamlId(y.id);
                              setClaimError(null);
                              try {
                                await releaseYaml(room.id, y.id);
                                await refresh();
                              } catch (e) {
                                setClaimError({ id: y.id, msg: e instanceof Error ? e.message : "Release failed" });
                              } finally {
                                setClaimingYamlId(null);
                              }
                            }}
                          >
                            {claimingYamlId === y.id ? "Releasing…" : "Release"}
                          </button>
                        )}
                        {claimedByOther && (
                          <span className="muted" style={{ fontSize: "0.78rem" }}>
                            Taken
                          </span>
                        )}
                        {isMine && room.status === "open" && (
                          <button
                            type="button"
                            className="btn btn-sm"
                            title="Edit your YAML in place (no need to delete + re-upload)"
                            onClick={() => setOpenYaml({ id: y.id, tab: "edit" })}
                          >
                            Edit
                          </button>
                        )}
                        {/* In claim_mode the "Delete" button doesn't make sense
                            for claimers - they just release the slot back.
                            Hidden when claim_mode is on; kept for normal rooms
                            where the row is the player's own upload. */}
                        {!room.claim_mode && isMine && room.status === "open" && (
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            disabled={deletingYamlId === y.id}
                            title="Delete your own submission"
                            onClick={async () => {
                              if (!confirm(`Delete your YAML for ${y.player_name}?`)) return;
                              setDeletingYamlId(y.id);
                              try {
                                await deletePublicYaml(room.id, y.id);
                                await refresh();
                              } catch (e) {
                                alert(e instanceof Error ? e.message : "Delete failed");
                              } finally {
                                setDeletingYamlId(null);
                              }
                            }}
                          >
                            {deletingYamlId === y.id ? "Deleting…" : "Delete"}
                          </button>
                        )}
                      </div>
                      {claimError?.id === y.id && (
                        <p className="error" style={{ margin: "0.25rem 0 0", fontSize: "0.78rem" }}>
                          {claimError.msg}
                        </p>
                      )}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </div>
      </details>

      {room.claim_mode ? (
        // FEAT-20: claim-mode rooms don't accept player uploads - players
        // claim slots the host pre-loaded. The login gate still applies if
        // require_discord_login is on (which is implicit anyway: claiming
        // requires being logged in).
        room.status === "open" && !user ? (
          <DiscordLoginGate roomId={room.id} />
        ) : null
      ) : room.status === "open" && room.require_discord_login && !user ? (
        <DiscordLoginGate roomId={room.id} />
      ) : (
        <SubmissionForm
          room={room}
          uploadFiles={uploadFiles}
          state={submitState}
          setState={setSubmitState}
          onSubmitted={refresh}
        />
      )}

      {room.seed && (room.status === "generated" || room.status === "playing") && (
        <p className="public-section" style={{ textAlign: "center" }}>
          <Link to={`/play/${room.seed}`} className="btn btn-primary">
            Connection details &amp; patches &rarr;
          </Link>
        </p>
      )}
    </div>
  );
}

export default RoomPublic;
