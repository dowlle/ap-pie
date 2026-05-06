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
  deadlineFromTimeOnly,
  type CreateRoomModalState,
} from "../lib/roomTemplates";
import RoomTemplateFields from "./RoomTemplateFields";

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
  // The room-name field lives inside `state` (not as a separate useState)
  // so templates can pre-fill it via payload.room_name.
  const [state, setState] = useState<CreateRoomModalState>(BLANK_MODAL_STATE);
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
    const proposed = state.name.trim() || "Untitled template";
    const tplName = window.prompt("Name this template:", proposed);
    if (tplName === null) return;  // host cancelled
    const trimmed = tplName.trim();
    if (!trimmed) {
      setTemplateMessage("Template name is required.");
      return;
    }
    setSavingTemplate(true);
    try {
      // Drop the absolute date at save-as time: templates capture only
      // the time-of-day with day_offset=0. The host can change the offset
      // later in the template editor if they want a recurring +N-days
      // pattern. Without this, every template saved from the create
      // modal would lock to whatever specific date the host happened to
      // pick for THAT room.
      const deadline = deadlineFromTimeOnly(state.deadlineLocal);
      const payload = captureTemplateFromModal(state, new Date(), deadline);
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
    if (!state.name.trim() || !hostName.trim() || submitting) return;
    setError("");
    setSubmitting(true);
    try {
      await createRoom({
        name: state.name.trim(),
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

  const canSubmit = !!hostName && !!state.name.trim() && !submitting;

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
              <h3>Start from a template</h3>
              <p className="settings-hint">
                Apply a saved template to pre-fill every field below. You can
                still tweak anything before clicking Create. Manage your
                templates from <em>My templates</em> on the Rooms page.
              </p>
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

          <RoomTemplateFields
            state={state}
            setState={setState}
            nameRequired
            namePlaceholder="Room name"
            autoFocusName
          />

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
            title="Save the current modal settings as a reusable template."
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
