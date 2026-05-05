import { useEffect, useMemo, useRef, useState } from "react";
import {
  requestApworldUpdateFromRoom,
  type Room,
  type APWorldInfo,
  type RoomAPWorldEntry,
} from "../api";

/**
 * Native <dialog> modal for FEAT-30 Phase 0a. The room host opens this
 * to request a new APWorld version be added to dowlle/Archipelago-index.
 *
 * Picker behaviour: derives a candidate APWorld list from the room's
 * YAMLs (which game string each YAML uses) and the room's existing
 * pins. The picker shows display names; the selection resolves to the
 * apworld_name (TOML basename) which the backend uses for routing.
 *
 * The picker does NOT filter by "needs an update" - the host might want
 * to nudge a version even when nothing's stale yet, and the determination
 * of "stale" depends on data the modal doesn't have. The header text
 * notes which row is currently flagged via the orange-warn pill so the
 * host has context.
 *
 * Per FEAT-30 design: this writes a row to the apworld_index_requests
 * queue. No GitHub work happens here - Appie triages the request from
 * /admin/apworld-requests, runs the Eijebong fuzzer + FEAT-19 audit on
 * Atlas, and opens the PR by hand. Atlas-worker automation is Phase 1.
 */
export default function RequestApworldUpdateModal({
  room,
  apworlds,
  pins,
  prefillApworldName,
  prefillVersion,
  onClose,
  onSubmitted,
}: {
  room: Room;
  apworlds: APWorldInfo[];
  pins: RoomAPWorldEntry[];
  prefillApworldName?: string;
  prefillVersion?: string;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  // Derive the picker's option list from the room's YAMLs joined against
  // the index. Each entry tracks the apworld_name (used for routing) and
  // the human-friendly display name (shown in the picker + sent to the
  // backend so the queue row carries it for the admin UI).
  const candidates = useMemo(() => {
    const seen = new Map<string, { apworld_name: string; display_name: string; current_pin?: string }>();
    const indexByDisplay = new Map<string, APWorldInfo>();
    for (const w of apworlds) indexByDisplay.set(w.display_name, w);
    const pinByApworld = new Map<string, string>();
    for (const p of pins) {
      const apw = p.apworld_name;
      const ver = p.selected_version;
      if (apw && ver) pinByApworld.set(apw, ver);
    }
    for (const y of room.yamls ?? []) {
      // YAMLs may have a slash-joined "Game A / Game B" multi-game string
      // (BUG-03 join). Split so each game gets its own picker entry.
      const games = (y.game ?? "").split(" / ").map((s) => s.trim()).filter(Boolean);
      for (const g of games) {
        const w = indexByDisplay.get(g);
        if (!w) continue;
        if (w.is_builtin) continue;
        if (seen.has(w.name)) continue;
        seen.set(w.name, {
          apworld_name: w.name,
          display_name: w.display_name,
          current_pin: pinByApworld.get(w.name),
        });
      }
    }
    return Array.from(seen.values()).sort((a, b) => a.display_name.localeCompare(b.display_name));
  }, [room.yamls, apworlds, pins]);

  const initialApworld =
    prefillApworldName && candidates.some((c) => c.apworld_name === prefillApworldName)
      ? prefillApworldName
      : candidates[0]?.apworld_name ?? "";

  const [apworldName, setApworldName] = useState(initialApworld);
  const [requestedVersion, setRequestedVersion] = useState(prefillVersion ?? "");
  const [sourceUrl, setSourceUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    const onCancel = (e: Event) => { e.preventDefault(); onClose(); };
    dlg.addEventListener("cancel", onCancel);
    return () => dlg.removeEventListener("cancel", onCancel);
  }, [onClose]);

  // Backdrop-click closes (matching the RoomSettingsModal pattern).
  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  const selected = candidates.find((c) => c.apworld_name === apworldName);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!apworldName) {
      setError("Pick an APWorld to request an update for");
      return;
    }
    if (!selected) {
      setError("Selected APWorld is no longer in the index");
      return;
    }
    if (!requestedVersion.trim()) {
      setError("Version is required");
      return;
    }
    if (!sourceUrl.trim()) {
      setError("Source URL is required");
      return;
    }
    setSubmitting(true);
    try {
      await requestApworldUpdateFromRoom(room.id, apworldName, {
        display_name: selected.display_name,
        requested_version: requestedVersion.trim(),
        source_url: sourceUrl.trim(),
        notes: notes.trim() || undefined,
      });
      onSubmitted();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Submit failed";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      className="settings-modal"
      onClick={onBackdropClick}
    >
      <form className="settings-modal-form" onSubmit={submit}>
        <header className="settings-modal-header">
          <div>
            <h2>Request APWorld update</h2>
            <p className="settings-modal-subtitle">
              Propose a new version for the dowlle/Archipelago-index. Appie reviews + runs the fuzzer + audit before merge.
            </p>
          </div>
          <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="settings-modal-body">
          {candidates.length === 0 ? (
            <section className="settings-section">
              <p className="muted">
                None of this room's YAMLs reference an indexed APWorld. Either every game is built-in /
                not yet in the index, or the YAMLs haven't been validated yet. Add the APWorld to the
                index first via a PR to <code>dowlle/Archipelago-index</code>, then come back here.
              </p>
            </section>
          ) : (
            <>
              <section className="settings-section">
                <label className="room-edit-row">
                  <span className="room-edit-label">APWorld</span>
                  <select
                    value={apworldName}
                    onChange={(e) => setApworldName(e.target.value)}
                    disabled={submitting}
                  >
                    {candidates.map((c) => (
                      <option key={c.apworld_name} value={c.apworld_name}>
                        {c.display_name}{c.current_pin ? `  (pinned: v${c.current_pin})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="muted" style={{ fontSize: "0.78rem", marginTop: "0.4rem" }}>
                  Only APWorlds referenced by a YAML in this room are listed.
                  Maintainers can also submit from the My APWorlds page (coming soon).
                </p>
              </section>

              <section className="settings-section">
                <label className="room-edit-row">
                  <span className="room-edit-label">New version</span>
                  <input
                    type="text"
                    placeholder="e.g. 3.6.0 or 0.10.10-beta"
                    value={requestedVersion}
                    onChange={(e) => setRequestedVersion(e.target.value)}
                    disabled={submitting}
                    maxLength={64}
                  />
                </label>
                <label className="room-edit-row">
                  <span className="room-edit-label">Release URL</span>
                  <input
                    type="url"
                    placeholder="https://github.com/.../release/download/v.../Name.apworld"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    disabled={submitting}
                    maxLength={1024}
                  />
                </label>
                <p className="muted" style={{ fontSize: "0.78rem" }}>
                  HTTPS link to the .apworld file. The fuzzer + audit run against this URL on Atlas.
                </p>
              </section>

              <section className="settings-section">
                <label className="room-edit-row" style={{ alignItems: "flex-start" }}>
                  <span className="room-edit-label">Notes (optional)</span>
                  <textarea
                    rows={3}
                    placeholder="Anything Appie should know - changelog highlights, known issues, why you need this version..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={submitting}
                    maxLength={2000}
                  />
                </label>
              </section>

              {error && <p style={{ color: "var(--accent-warn)" }}>{error}</p>}
            </>
          )}
        </div>

        <footer className="settings-modal-footer">
          <button type="button" className="btn" onClick={onClose} disabled={submitting}>Cancel</button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || candidates.length === 0}
          >
            {submitting ? "Submitting..." : "Submit request"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
