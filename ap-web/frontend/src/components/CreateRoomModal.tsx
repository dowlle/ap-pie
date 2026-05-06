import { useEffect, useRef, useState } from "react";
import {
  createRoom,
  createRoomTemplate,
  listRoomTemplates,
  type RoomTemplate,
} from "../api";
import { useAuth } from "../context/AuthContext";
import { localInputValueToIso } from "../lib/roomDeadline";
import {
  applyTemplateToModal,
  BLANK_MODAL_STATE,
  captureTemplateFromModal,
  type CreateRoomModalState,
} from "../lib/roomTemplates";
import MarkdownText from "./MarkdownText";

/**
 * Native <dialog> create-room modal. Same lifecycle and visual chrome as
 * RoomSettingsModal: showModal once on mount, ESC-to-cancel via the cancel
 * event, backdrop click closes via target check, sectioned cards in the
 * body, primary action in the sticky footer.
 *
 * FEAT-33: room-shape settings (claim_mode, max_yamls_per_user) live here
 * at create time too, not just in RoomSettingsModal post-create. The
 * "Select template..." dropdown at the top applies a saved template to
 * every field; "Save as template" in the footer captures current state as
 * a new template (prompting for a name). The user's default template, if
 * any, auto-applies on modal open.
 *
 * Race mode + spoiler level are intentionally omitted: they're generation-
 * feature concerns and Archipelago Pie ships as a YAML collector only on
 * ap-pie.com. New rooms get the backend defaults (spoiler_level=3,
 * race_mode=false) which existing room views still render unchanged.
 */
function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <h3>{title}</h3>
      <p className="settings-hint">{hint}</p>
    </>
  );
}

export default function CreateRoomModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const { user } = useAuth();

  // Modal state mirrors lib/roomTemplates' CreateRoomModalState shape so
  // applyTemplateToModal/captureTemplateFromModal can round-trip cleanly.
  const [state, setState] = useState<CreateRoomModalState>(BLANK_MODAL_STATE);
  const [name, setName] = useState("");
  const [descPreview, setDescPreview] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Templates: list, current selection, and a save-status message for the
  // "Save as template" button.
  const [templates, setTemplates] = useState<RoomTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | "">("");
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateMessage, setTemplateMessage] = useState("");

  const hostName = user?.discord_username ?? "";

  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  // Open / close the native <dialog>.
  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (open && !dlg.open) {
      dlg.showModal();
    } else if (!open && dlg.open) {
      dlg.close();
    }
    const onCancel = (e: Event) => { e.preventDefault(); onCloseRef.current(); };
    dlg.addEventListener("cancel", onCancel);
    return () => {
      dlg.removeEventListener("cancel", onCancel);
    };
  }, [open]);

  // Reset fields whenever the modal opens, then load templates and apply the
  // user's default template (if any) so they don't have to pick from the
  // dropdown every time.
  useEffect(() => {
    if (!open) return;
    setName("");
    setState(BLANK_MODAL_STATE);
    setSelectedTemplateId("");
    setError("");
    setSubmitting(false);
    setSavingTemplate(false);
    setTemplateMessage("");

    let cancelled = false;
    listRoomTemplates()
      .then(({ templates }) => {
        if (cancelled) return;
        setTemplates(templates);
        const def = templates.find(t => t.is_default);
        if (def) {
          setSelectedTemplateId(def.id);
          setState(applyTemplateToModal(def.payload, new Date()));
        }
      })
      .catch(() => {
        // Network or 401 (logged-out) — silently fall through to a blank modal.
      });
    return () => { cancelled = true; };
  }, [open]);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  // Apply a template's payload to the modal when the host picks one from
  // the dropdown. The deadline pre-fills via the smart helper but the
  // datetime-local field stays editable.
  const handleTemplatePick = (id: number | "") => {
    setSelectedTemplateId(id);
    setTemplateMessage("");
    if (id === "") return;
    const tmpl = templates.find(t => t.id === id);
    if (!tmpl) return;
    setState(applyTemplateToModal(tmpl.payload, new Date()));
  };

  const handleSaveAsTemplate = async () => {
    setError("");
    setTemplateMessage("");
    const proposed = name.trim() || "Untitled template";
    const tplName = window.prompt("Name this template:", proposed);
    if (tplName === null) return;  // host cancelled
    const trimmed = tplName.trim();
    if (!trimmed) {
      setTemplateMessage("Template name is required.");
      return;
    }
    setSavingTemplate(true);
    try {
      const payload = captureTemplateFromModal(state, new Date());
      const created = await createRoomTemplate({ name: trimmed, payload });
      setTemplates(prev => [...prev, created]);
      setSelectedTemplateId(created.id);
      setTemplateMessage(`Saved as "${created.name}".`);
    } catch (err) {
      setTemplateMessage(err instanceof Error ? err.message : "Couldn't save template.");
    } finally {
      setSavingTemplate(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !hostName.trim() || submitting) return;
    setError("");
    setSubmitting(true);
    try {
      await createRoom({
        name: name.trim(),
        host_name: hostName,
        description: state.description,
        require_discord_login: state.requireDiscordLogin,
        claim_mode: state.claimMode,
        max_yamls_per_user: state.maxYamlsPerUser,
        submit_deadline: localInputValueToIso(state.deadlineLocal),
        // Send both display flags atomically so the radio's invariants
        // (exactly one of strict / flexible / latest) hold server-side.
        allow_mixed_apworld_versions: state.policyMode === "flexible",
        force_latest_apworld_versions: state.policyMode === "latest",
        auto_upgrade_apworld_pins: state.autoUpgrade,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = !!hostName && !!name.trim() && !submitting;

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal">
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Create room</strong>
          {hostName && (
            <span className="settings-modal-meta">Hosting as {hostName}</span>
          )}
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <form onSubmit={handleSubmit} style={{ display: "contents" }}>
        <div className="settings-modal-body">
          {templates.length > 0 && (
            <section className="settings-section">
              <SectionHeader
                title="Start from a template"
                hint="Apply a saved template to pre-fill every field below. You can still tweak anything before clicking Create. Manage your templates from the My templates page."
              />
              <div className="settings-controls">
                <select
                  value={selectedTemplateId}
                  onChange={(e) => handleTemplatePick(e.target.value === "" ? "" : parseInt(e.target.value, 10))}
                  style={{ flex: 1, minWidth: "12rem" }}
                >
                  <option value="">Select template...</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.name}{t.is_default ? " (default)" : ""}
                    </option>
                  ))}
                </select>
              </div>
            </section>
          )}

          <section className="settings-section">
            <SectionHeader
              title="Room basics"
              hint="The name shows up in the rooms list and on the public room page. Description is optional and rendered above the YAML list for context."
            />
            <div className="settings-controls">
              <input
                type="text"
                placeholder="Room name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="settings-controls">
              <div className="markdown-edit-shell" style={{ flex: 1, minWidth: "12rem" }}>
                <div className="markdown-edit-toolbar">
                  <button
                    type="button"
                    className={`markdown-edit-tab ${descPreview ? "" : "is-active"}`}
                    onClick={() => setDescPreview(false)}
                  >Edit</button>
                  <button
                    type="button"
                    className={`markdown-edit-tab ${descPreview ? "is-active" : ""}`}
                    onClick={() => setDescPreview(true)}
                    disabled={!state.description.trim()}
                    title={!state.description.trim() ? "Nothing to preview yet" : "Preview rendered markdown"}
                  >Preview</button>
                  <span className="markdown-edit-hint">markdown supported</span>
                </div>
                {descPreview ? (
                  <div className="markdown-edit-preview">
                    <MarkdownText source={state.description} />
                  </div>
                ) : (
                  <textarea
                    placeholder="Description (optional, markdown supported)"
                    value={state.description}
                    onChange={(e) => setState(s => ({ ...s, description: e.target.value }))}
                    rows={3}
                    style={{
                      width: "100%",
                      fontFamily: "inherit",
                      fontSize: "0.85rem",
                      padding: "0.4rem 0.6rem",
                      border: "1px solid var(--border)",
                      borderRadius: 6,
                      background: "var(--bg)",
                      color: "var(--text)",
                      resize: "vertical",
                    }}
                  />
                )}
              </div>
            </div>
          </section>

          <section className="settings-section">
            <SectionHeader
              title="Require Discord login to submit"
              hint="When on, players must log in with Discord before submitting a YAML. You'll see their Discord identity next to every submission. Can be toggled later in Room settings."
            />
            <div className="settings-controls">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={state.requireDiscordLogin}
                  onChange={(e) => setState(s => ({ ...s, requireDiscordLogin: e.target.checked }))}
                />
                <span>Login required</span>
              </label>
            </div>
          </section>

          <section className="settings-section">
            <SectionHeader
              title="Claim mode"
              hint="When on, you pre-load YAMLs anonymously and players claim slots from the public lobby. Useful for bulk pre-loading a game pool and letting your group pick. Can be toggled later in Room settings."
            />
            <div className="settings-controls">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={state.claimMode}
                  onChange={(e) => setState(s => ({ ...s, claimMode: e.target.checked }))}
                />
                <span>Players claim pre-loaded slots</span>
              </label>
            </div>
          </section>

          <section className="settings-section">
            <SectionHeader
              title="Per-user submission cap"
              hint="Maximum YAMLs each Discord user can submit. 0 = unlimited. Anonymous submits ignore this cap (no identity to count). Only meaningful when paired with login required."
            />
            <div className="settings-controls">
              <input
                type="number"
                min={0}
                max={9999}
                step={1}
                value={state.maxYamlsPerUser}
                onChange={(e) => setState(s => ({
                  ...s,
                  maxYamlsPerUser: Math.max(0, parseInt(e.target.value || "0", 10) || 0),
                }))}
                style={{ width: "8rem" }}
              />
              <span className="settings-aux-note" style={{ margin: 0 }}>
                {state.maxYamlsPerUser === 0 ? "Unlimited" : `${state.maxYamlsPerUser} per Discord user`}
              </span>
            </div>
          </section>

          <section className="settings-section">
            <SectionHeader
              title="Auto-close deadline"
              hint="Optional. The room auto-closes at this date/time in your local timezone, and players see a countdown on the public page. You can still close manually before then, or clear the deadline later in Room settings."
            />
            <div className="settings-controls">
              <input
                type="datetime-local"
                value={state.deadlineLocal}
                onChange={(e) => setState(s => ({ ...s, deadlineLocal: e.target.value }))}
              />
              {state.deadlineLocal && (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => setState(s => ({ ...s, deadlineLocal: "" }))}
                  title="Clear the auto-close deadline"
                >
                  Clear
                </button>
              )}
            </div>
          </section>

          <section className="settings-section">
            <SectionHeader
              title="APWorld version policy"
              hint="Pick how strictly per-game APWorld version pins are presented to players. The radio options are mutually exclusive; auto-upgrade below is an orthogonal write-time setting. All three can be changed later in Room settings."
            />

            <div className="settings-controls" style={{ flexDirection: "column", alignItems: "flex-start", gap: "0.6rem" }}>
              <label className="settings-toggle">
                <input
                  type="radio"
                  name="create-apworld-policy"
                  value="strict"
                  checked={state.policyMode === "strict"}
                  onChange={() => setState(s => ({ ...s, policyMode: "strict" }))}
                />
                <span>
                  <strong>Pin specific versions</strong> (default): players see "install version X" for
                  each pinned game.
                </span>
              </label>

              <label className="settings-toggle">
                <input
                  type="radio"
                  name="create-apworld-policy"
                  value="flexible"
                  checked={state.policyMode === "flexible"}
                  onChange={() => setState(s => ({ ...s, policyMode: "flexible" }))}
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
                  name="create-apworld-policy"
                  value="latest"
                  checked={state.policyMode === "latest"}
                  onChange={() => setState(s => ({ ...s, policyMode: "latest" }))}
                />
                <span>
                  <strong>Always use the newest version</strong>: ignores per-game pins, always tells
                  players to install whatever's currently latest in the index.
                </span>
              </label>
            </div>

            <div className="settings-controls" style={{ marginTop: "0.6rem" }}>
              <label className="settings-toggle" style={{ opacity: state.policyMode === "latest" ? 0.55 : 1 }}>
                <input
                  type="checkbox"
                  checked={state.autoUpgrade}
                  disabled={state.policyMode === "latest"}
                  onChange={(e) => setState(s => ({ ...s, autoUpgrade: e.target.checked }))}
                />
                <span>Auto-upgrade pins to newest YAML version</span>
              </label>
            </div>
            <p className="settings-aux-note">
              On by default. When a YAML uploads with a `requires.game.&lt;Name&gt;` version higher
              than the current pin, the pin bumps up to match.
              {state.policyMode === "latest" && (
                <>
                  {" "}
                  <em>Greyed out while "Always use the newest version" is selected: there are no
                  pins to upgrade.</em>
                </>
              )}
            </p>
          </section>

          {error && (
            <p className="settings-error" style={{ margin: 0 }}>{error}</p>
          )}
          {templateMessage && (
            <p className="settings-aux-note" style={{ margin: 0 }}>{templateMessage}</p>
          )}
        </div>

        <footer className="settings-modal-footer">
          <button type="button" className="btn btn-sm" onClick={onClose}>Cancel</button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={handleSaveAsTemplate}
            disabled={savingTemplate}
            title="Save the current modal settings (everything except the room name) as a reusable template."
          >
            {savingTemplate ? "Saving..." : "Save as template"}
          </button>
          <button
            type="submit"
            className="btn btn-sm btn-primary"
            disabled={!canSubmit}
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
