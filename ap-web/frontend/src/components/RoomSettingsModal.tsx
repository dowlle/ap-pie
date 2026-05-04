import { useEffect, useRef, useState } from "react";
import {
  autoPinAllAPWorlds,
  getRoomAPWorlds,
  setRoomAPWorld,
  updateRoom,
  type AutoPinAllResult,
  type Room,
  type RoomAPWorldEntry,
} from "../api";

/**
 * Consolidates the host-only "knobs" on a room into one modal:
 *   1. Require Discord login to submit
 *   2. Claim mode (FEAT-20) - host pre-loads anonymous YAMLs for player claim
 *   3. External AP server (host:port pointer)
 *   4. Per-Discord-user submission cap (FEAT-07)
 *   5. External Archipelago tracker URL (FEAT-08)
 *   6. Tracker slot override (FEAT-17)
 *   7. APWorld version pins (FEAT-21) - per-game version players need
 *
 * Each section saves independently - no "Save all" button. Closing the
 * modal doesn't roll back changes; saved sections stay saved.
 *
 * Implemented as a native <dialog> for parity with YamlModal - gives us
 * focus trap, ESC-to-close, and backdrop styling for free.
 */
type TabKey = "general" | "apworlds" | "tracker";

export default function RoomSettingsModal({
  room,
  onClose,
  onUpdate,
}: {
  room: Room;
  onClose: () => void;
  onUpdate: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [tab, setTab] = useState<TabKey>("general");

  // Same fix as YamlModal: parent re-renders pass new inline onClose
  // refs which would otherwise tear down + re-open the dialog (focus
  // loss, flicker). Lifecycle pinned to mount/unmount; cancel handler
  // reads onClose via ref for the latest value.
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    const onCancel = (e: Event) => { e.preventDefault(); onCloseRef.current(); };
    dlg.addEventListener("cancel", onCancel);
    return () => {
      dlg.removeEventListener("cancel", onCancel);
      if (dlg.open) dlg.close();
    };
  }, []);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal">
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Room settings</strong>
          <span className="settings-modal-meta">{room.name}</span>
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <nav className="settings-modal-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "general"}
          className={`settings-tab${tab === "general" ? " active" : ""}`}
          onClick={() => setTab("general")}
        >
          General
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "apworlds"}
          className={`settings-tab${tab === "apworlds" ? " active" : ""}`}
          onClick={() => setTab("apworlds")}
        >
          APWorlds
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "tracker"}
          className={`settings-tab${tab === "tracker" ? " active" : ""}`}
          onClick={() => setTab("tracker")}
        >
          Tracker
        </button>
      </nav>

      <div className="settings-modal-body">
        {tab === "general" && (
          <>
            <DiscordLoginSection room={room} onUpdate={onUpdate} />
            <ClaimModeSection room={room} onUpdate={onUpdate} />
            <ExternalServerSection room={room} onUpdate={onUpdate} />
            <PerUserCapSection room={room} onUpdate={onUpdate} />
          </>
        )}
        {tab === "apworlds" && (
          <>
            <APWorldsPolicySection room={room} onUpdate={onUpdate} />
            <APWorldsSection room={room} />
          </>
        )}
        {tab === "tracker" && (
          <>
            <TrackerUrlSection room={room} onUpdate={onUpdate} />
            <TrackerSlotOverrideSection room={room} onUpdate={onUpdate} />
          </>
        )}
      </div>

      <footer className="settings-modal-footer">
        <button type="button" className="btn btn-sm btn-primary" onClick={onClose}>Done</button>
      </footer>
    </dialog>
  );
}

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <h3>{title}</h3>
      <p className="settings-hint">{hint}</p>
    </>
  );
}

function SavedHint({ visible }: { visible: boolean }) {
  if (!visible) return null;
  return <span className="settings-saved">✓ saved</span>;
}

function DiscordLoginSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const toggle = async (next: boolean) => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      await updateRoom(room.id, { require_discord_login: next });
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="Require Discord login to submit"
        hint="When on, players must log in with Discord before submitting a YAML. You'll see their Discord identity next to every submission."
      />
      <div className="settings-controls">
        <label className="settings-toggle">
          <input
            type="checkbox"
            checked={!!room.require_discord_login}
            disabled={saving}
            onChange={(e) => toggle(e.target.checked)}
          />
          <span>Login required</span>
        </label>
        <SavedHint visible={savedHint} />
      </div>
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function ClaimModeSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const toggle = async (next: boolean) => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      await updateRoom(room.id, { claim_mode: next });
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="Claim mode"
        hint={
          "When on, YAMLs you upload land as anonymous slots. Logged-in players visiting the room page can claim any slot they want " +
          "(host's choice of game, player's choice of which one). The per-player cap below still applies. Already-uploaded YAMLs aren't retroactively unclaimed - toggle this BEFORE bulk-uploading the pool."
        }
      />
      <div className="settings-controls">
        <label className="settings-toggle">
          <input
            type="checkbox"
            checked={!!room.claim_mode}
            disabled={saving}
            onChange={(e) => toggle(e.target.checked)}
          />
          <span>Players claim slots</span>
        </label>
        <SavedHint visible={savedHint} />
      </div>
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function ExternalServerSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [host, setHost] = useState(room.external_host ?? "");
  const [port, setPort] = useState(room.external_port ? String(room.external_port) : "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const save = async () => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      const trimmedHost = host.trim();
      const portNum = port.trim() === "" ? null : Number(port);
      if (trimmedHost && (portNum === null || isNaN(portNum) || portNum < 1 || portNum > 65535)) {
        setErr("Port must be 1-65535");
        setSaving(false);
        return;
      }
      await updateRoom(room.id, {
        external_host: trimmedHost || null,
        external_port: trimmedHost ? portNum : null,
      });
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const clear = async () => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      await updateRoom(room.id, { external_host: null, external_port: null });
      setHost("");
      setPort("");
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to clear");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="External AP server"
        hint="Where the Archipelago server runs (your machine or a hosted instance). Players see this on the room page so they can connect."
      />
      <div className="settings-controls">
        <input
          type="text"
          placeholder="host or ap.example.com"
          value={host}
          onChange={(e) => setHost(e.target.value)}
          disabled={saving}
        />
        <input
          type="number"
          placeholder="port"
          value={port}
          onChange={(e) => setPort(e.target.value)}
          disabled={saving}
          min={1}
          max={65535}
        />
        <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>Save</button>
        {(room.external_host || room.external_port) && (
          <button className="btn btn-sm btn-danger" onClick={clear} disabled={saving}>Clear</button>
        )}
        <SavedHint visible={savedHint} />
      </div>
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function PerUserCapSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [value, setValue] = useState(String(room.max_yamls_per_user ?? 0));
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const save = async () => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      const n = Math.max(0, Math.floor(Number(value) || 0));
      await updateRoom(room.id, { max_yamls_per_user: n });
      setValue(String(n));
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="Per-player submission cap"
        hint={
          "Maximum YAMLs each Discord user can submit. 0 = unlimited. " +
          "Anonymous submits aren't counted (no identity to attribute) - pair with Login required for full enforcement."
        }
      />
      <div className="settings-controls">
        <input
          type="number"
          min={0}
          step={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={saving}
        />
        <span className="settings-hint" style={{ marginRight: "auto" }}>YAMLs / Discord user</span>
        <button className="btn btn-sm btn-primary" onClick={save} disabled={saving}>Save</button>
        <SavedHint visible={savedHint} />
      </div>
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function TrackerUrlSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [value, setValue] = useState(room.tracker_url ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const save = async (next: string | null) => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      await updateRoom(room.id, { tracker_url: next });
      setValue(next ?? "");
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="Live tracker URL"
        hint={
          "Paste an archipelago.gg tracker URL. The room page surfaces a live dashboard with per-player checks, completion %, and connection status. " +
          "Per-slot items / locations / hints are also exposed via the per-card detail modal (FEAT-14)."
        }
      />
      <div className="settings-controls">
        <input
          type="url"
          placeholder="https://archipelago.gg/tracker/..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={saving}
        />
        <button
          className="btn btn-sm btn-primary"
          onClick={() => save(value.trim() || null)}
          disabled={saving}
        >
          Save
        </button>
        {room.tracker_url && (
          <button className="btn btn-sm btn-danger" onClick={() => save(null)} disabled={saving}>
            Clear
          </button>
        )}
        <SavedHint visible={savedHint} />
      </div>
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function TrackerSlotOverrideSection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  const [value, setValue] = useState(room.tracker_slot_name ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [savedHint, setSavedHint] = useState(false);

  const save = async (next: string | null) => {
    setSaving(true);
    setErr("");
    setSavedHint(false);
    try {
      await updateRoom(room.id, { tracker_slot_name: next });
      setValue(next ?? "");
      setSavedHint(true);
      onUpdate();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="Tracker slot override"
        hint={
          "Optional. Names the in-game slot the WebSocket tracker connection will authenticate as. " +
          "Leave blank to auto-pick (your first uploaded slot in this room, or the first slot scraped from the tracker page if none of your YAMLs match). " +
          "Saving here will bounce the active connection so the new slot takes effect immediately - that posts one Join line into the AP server's chat."
        }
      />
      <div className="settings-controls">
        <input
          type="text"
          placeholder="e.g. AppieRefunct"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={saving || !room.tracker_url}
        />
        <button
          className="btn btn-sm btn-primary"
          onClick={() => save(value.trim() || null)}
          disabled={saving || !room.tracker_url}
        >
          Save
        </button>
        {room.tracker_slot_name && (
          <button className="btn btn-sm btn-danger" onClick={() => save(null)} disabled={saving}>
            Clear
          </button>
        )}
        <SavedHint visible={savedHint} />
      </div>
      {!room.tracker_url && (
        <p className="settings-aux-note">Set a Live tracker URL above first.</p>
      )}
      {err && <p className="settings-error">{err}</p>}
    </section>
  );
}

function APWorldsSection({ room }: { room: Room }) {
  // FEAT-21: pin a specific APWorld version per game in the room. Auto-derived
  // from the YAMLs uploaded so far - one row per distinct game string. The
  // public room page shows pinned entries to players as install links.
  const [entries, setEntries] = useState<RoomAPWorldEntry[] | null>(null);
  const [loadErr, setLoadErr] = useState("");
  const [savingFor, setSavingFor] = useState<string | null>(null);
  const [rowErr, setRowErr] = useState<Record<string, string>>({});
  const [savedFor, setSavedFor] = useState<string | null>(null);
  // FEAT-21 follow-up: retroactive auto-pin button. Same logic the
  // upload path already runs per YAML, but for the whole room at once -
  // useful for rooms created before auto-pin shipped or after the index
  // gains new entries.
  const [autoPinning, setAutoPinning] = useState(false);
  const [autoPinResult, setAutoPinResult] = useState<AutoPinAllResult | null>(null);
  const [autoPinErr, setAutoPinErr] = useState("");

  const load = () => {
    getRoomAPWorlds(room.id)
      .then((data) => { setEntries(data); setLoadErr(""); })
      .catch((e) => setLoadErr(e instanceof Error ? e.message : "Failed to load APWorlds"));
  };

  const runAutoPinAll = async () => {
    setAutoPinning(true);
    setAutoPinErr("");
    setAutoPinResult(null);
    try {
      const result = await autoPinAllAPWorlds(room.id);
      setAutoPinResult(result);
      load();
    } catch (e) {
      setAutoPinErr(e instanceof Error ? e.message : "Auto-pin failed");
    } finally {
      setAutoPinning(false);
    }
  };

  // Re-fetch when force-latest flips: the backend recomputes selected_version
  // off the index instead of stored pins, so we want fresh data shown.
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ },
    [room.id, room.force_latest_apworld_versions]);

  const save = async (apworldName: string, version: string | null) => {
    setSavingFor(apworldName);
    setRowErr((m) => ({ ...m, [apworldName]: "" }));
    try {
      await setRoomAPWorld(room.id, apworldName, version);
      setSavedFor(apworldName);
      setTimeout(() => setSavedFor((s) => (s === apworldName ? null : s)), 1500);
      load();
    } catch (e) {
      setRowErr((m) => ({
        ...m,
        [apworldName]: e instanceof Error ? e.message : "Failed to save",
      }));
    } finally {
      setSavingFor(null);
    }
  };

  return (
    <section className="settings-section">
      <SectionHeader
        title="APWorlds for this room"
        hint={
          "For each game the room's YAMLs use, pick which version of the APWorld your players should install. " +
          "Pinned versions surface on the public room page as one-click install links. " +
          "Games not in the index won't have a dropdown - drop the .apworld through your usual channel for now."
        }
      />

      {loadErr && <p className="settings-error">{loadErr}</p>}

      {entries !== null && entries.length > 0 && (
        <div className="settings-controls" style={{ marginBottom: "0.6rem" }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={runAutoPinAll}
            disabled={autoPinning}
            title="Pin the latest indexed version for every game in this room that doesn't have a pin yet. Won't touch games you've already pinned manually."
          >
            {autoPinning ? "Auto-pinning..." : "Auto-pin from index"}
          </button>
          {autoPinResult && (
            <span className="settings-aux-note" style={{ margin: 0 }}>
              Pinned {autoPinResult.pinned.length}
              {(autoPinResult.upgraded?.length ?? 0) > 0 &&
                ` · upgraded ${autoPinResult.upgraded?.length}`}
              {autoPinResult.pinned_with_yaml_version.length > 0 &&
                ` (${autoPinResult.pinned_with_yaml_version.length} from YAML version)`}
              {autoPinResult.skipped_already_pinned.length > 0 &&
                ` · ${autoPinResult.skipped_already_pinned.length} already pinned`}
              {(autoPinResult.skipped_locked?.length ?? 0) > 0 &&
                ` · ${autoPinResult.skipped_locked?.length} locked`}
              {(autoPinResult.skipped_builtin?.length ?? 0) > 0 &&
                ` · ${autoPinResult.skipped_builtin?.length} core`}
              {autoPinResult.skipped_not_in_index.length > 0 &&
                ` · ${autoPinResult.skipped_not_in_index.length} not in index`}
            </span>
          )}
        </div>
      )}
      {autoPinErr && <p className="settings-error">{autoPinErr}</p>}

      {entries === null ? (
        <p className="settings-aux-note">Loading...</p>
      ) : entries.length === 0 ? (
        <p className="settings-aux-note">
          No YAMLs uploaded yet - this list populates from each YAML's <code>game:</code> key.
        </p>
      ) : (
        <ul className="apworld-pin-list">
          {entries.map((e) => (
            <li key={e.game} className="apworld-pin-row">
              <div className="apworld-pin-game">
                <strong>{e.display_name}</strong>
                {e.display_name !== e.game && (
                  <span className="muted apworld-pin-raw">{e.game}</span>
                )}
                <span className="muted apworld-pin-count">
                  {e.yaml_count} YAML{e.yaml_count === 1 ? "" : "s"}
                </span>
                {e.tags.map((t) => <span key={t} className="tag">{t}</span>)}
              </div>

              {!e.in_index ? (
                <span className="muted apworld-pin-missing">Not in the index</span>
              ) : e.available_versions.length === 0 ? (
                <span className="muted apworld-pin-missing">Built-in only - no version pin needed</span>
              ) : (
                <div className="apworld-pin-controls">
                  <select
                    value={e.selected_version ?? ""}
                    disabled={savingFor === e.apworld_name || e.auto_latest}
                    onChange={(ev) => {
                      const v = ev.target.value;
                      if (v === "") {
                        save(e.apworld_name!, null);
                      } else {
                        save(e.apworld_name!, v);
                      }
                    }}
                  >
                    <option value="">- no pin -</option>
                    {e.available_versions.map((v) => (
                      <option key={v.version} value={v.version}>
                        v{v.version} ({v.source})
                      </option>
                    ))}
                  </select>
                  {e.auto_latest && (
                    <span className="settings-aux-note" style={{ margin: 0 }}>
                      auto: latest
                    </span>
                  )}
                  {e.selected_version && e.download_url && (
                    <a className="btn btn-sm" href={e.download_url} download>Preview</a>
                  )}
                  {e.home && (
                    <a className="btn btn-sm" href={e.home} target="_blank" rel="noreferrer">Source</a>
                  )}
                  {savedFor === e.apworld_name && <span className="settings-saved">saved</span>}
                </div>
              )}

              {rowErr[e.apworld_name ?? ""] && (
                <p className="settings-error">{rowErr[e.apworld_name ?? ""]}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type PolicyMode = "strict" | "flexible" | "latest";

function deriveMode(room: Room): PolicyMode {
  // force_latest dominates: if it's on, the other display flag is ignored
  // by `apworlds_for_room` regardless of value, so we model "latest" as a
  // single mode. allow_mixed alone (with force off) is "flexible". Neither
  // is "strict" (the default).
  if (room.force_latest_apworld_versions) return "latest";
  if (room.allow_mixed_apworld_versions) return "flexible";
  return "strict";
}

function APWorldsPolicySection({ room, onUpdate }: { room: Room; onUpdate: () => void }) {
  // The three storage flags (allow_mixed, force_latest, auto_upgrade) used
  // to expose as three independent checkboxes, which produced incoherent
  // combinations: force-latest + allow-mixed is redundant ("everyone install
  // latest, but it's just a suggestion"); force-latest + auto-upgrade is
  // wasted work (pins maintained but never displayed). The three coherent
  // modes are rendered as a radio group; auto-upgrade stays as an
  // orthogonal sub-toggle that's only meaningful in strict / flexible modes.
  // Storage is unchanged; the UI just enforces the valid combinations on save.
  const [savingMode, setSavingMode] = useState(false);
  const [savingUpgrade, setSavingUpgrade] = useState(false);
  const [errMode, setErrMode] = useState("");
  const [errUpgrade, setErrUpgrade] = useState("");
  const [savedHintMode, setSavedHintMode] = useState(false);
  const [savedHintUpgrade, setSavedHintUpgrade] = useState(false);

  const mode = deriveMode(room);

  const setMode = async (next: PolicyMode) => {
    if (next === mode) return;
    setSavingMode(true);
    setErrMode("");
    setSavedHintMode(false);
    try {
      // Send both flags atomically so the room never lands in a transient
      // (force=true, mixed=true) state between two single-flag PUTs.
      await updateRoom(room.id, {
        allow_mixed_apworld_versions: next === "flexible",
        force_latest_apworld_versions: next === "latest",
      });
      setSavedHintMode(true);
      onUpdate();
    } catch (e) {
      setErrMode(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSavingMode(false);
    }
  };

  const toggleAutoUpgrade = async (next: boolean) => {
    setSavingUpgrade(true);
    setErrUpgrade("");
    setSavedHintUpgrade(false);
    try {
      await updateRoom(room.id, { auto_upgrade_apworld_pins: next });
      setSavedHintUpgrade(true);
      onUpdate();
    } catch (e) {
      setErrUpgrade(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSavingUpgrade(false);
    }
  };

  // auto_upgrade is meaningless in "latest" mode (no pins to upgrade), so
  // we grey out the toggle there. The stored value is preserved either way
  // so flipping back to strict / flexible restores the host's preference.
  const upgradeDisabled = mode === "latest" || savingUpgrade;

  return (
    <section className="settings-section">
      <SectionHeader
        title="APWorld version policy"
        hint="Pick how strictly per-game APWorld version pins are presented to players. The radio options are mutually exclusive; auto-upgrade below is an orthogonal write-time setting."
      />

      <div className="settings-controls" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.6rem" }}>
        <label className="settings-toggle">
          <input
            type="radio"
            name={`apworld-policy-${room.id}`}
            value="strict"
            checked={mode === "strict"}
            disabled={savingMode}
            onChange={() => setMode("strict")}
          />
          <span>
            <strong>Pin specific versions</strong> (default): players see "install version X" for
            each pinned game.
          </span>
        </label>

        <label className="settings-toggle">
          <input
            type="radio"
            name={`apworld-policy-${room.id}`}
            value="flexible"
            checked={mode === "flexible"}
            disabled={savingMode}
            onChange={() => setMode("flexible")}
          />
          <span>
            <strong>Pin specific versions, but flexible</strong>: same pins, framed as "suggested"
            so players know they can deviate. Use when your players might upload different apworld
            versions and still need to discuss which version to use.
          </span>
        </label>

        <label className="settings-toggle">
          <input
            type="radio"
            name={`apworld-policy-${room.id}`}
            value="latest"
            checked={mode === "latest"}
            disabled={savingMode}
            onChange={() => setMode("latest")}
          />
          <span>
            <strong>Always use the newest version</strong>: ignores per-game pins, always tells
            players to install whatever's currently latest in the index. Manual pinning below is
            disabled while this is on.
          </span>
        </label>
        <SavedHint visible={savedHintMode} />
      </div>
      {errMode && <p className="settings-error">{errMode}</p>}

      <div className="settings-controls" style={{ marginTop: "0.6rem" }}>
        <label className="settings-toggle" style={{ opacity: mode === "latest" ? 0.55 : 1 }}>
          <input
            type="checkbox"
            checked={room.auto_upgrade_apworld_pins ?? true}
            disabled={upgradeDisabled}
            onChange={(e) => toggleAutoUpgrade(e.target.checked)}
          />
          <span>Auto-upgrade pins to newest YAML version</span>
        </label>
        <SavedHint visible={savedHintUpgrade} />
      </div>
      <p className="settings-aux-note">
        On by default. When a YAML uploads with a `requires.game.&lt;Name&gt;` version higher than
        the current pin, the pin bumps up to match. Includes manual picks: turn this off to lock
        pins exactly where you set them. The Version column on the room overview still shows
        orange warnings for mismatched YAMLs either way.
        {mode === "latest" && (
          <>
            {" "}
            <em>Greyed out while "Always use the newest version" is selected: there are no pins
            to upgrade.</em>
          </>
        )}
      </p>
      {errUpgrade && <p className="settings-error">{errUpgrade}</p>}
    </section>
  );
}
