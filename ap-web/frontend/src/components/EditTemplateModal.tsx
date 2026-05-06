import { useEffect, useRef, useState } from "react";
import {
  updateRoomTemplate,
  type RoomTemplate,
  type RoomTemplatePayload,
} from "../api";
import {
  applyTemplateToModal,
  BLANK_MODAL_STATE,
  captureTemplateFromModal,
  type CreateRoomModalState,
} from "../lib/roomTemplates";
import RoomTemplateFields from "./RoomTemplateFields";

/**
 * FEAT-33 iteration 2: edit an existing room template's payload from the
 * /rooms/templates page. Same form-field rendering as CreateRoomModal via
 * the shared <RoomTemplateFields> component, plus a separate "Template
 * name" input at the top (the label, not the room-name pre-fill — that
 * lives inside the body's room-name field).
 *
 * Deadline UI here is intentionally different from CreateRoomModal: instead
 * of an absolute datetime-local picker, we expose the template's intent
 * directly — a time-of-day + day-offset pair. Templates store relative
 * deadlines so they survive across "today"s; this UI lets the host edit
 * the relative shape directly without a confusing datetime round-trip
 * through "today".
 */

const DEFAULT_DEADLINE: RoomTemplatePayload["deadline"] = {
  enabled: false,
  time_of_day: "19:00",
  day_offset: 0,
};

export default function EditTemplateModal({
  template,
  open,
  onClose,
  onSaved,
}: {
  template: RoomTemplate | null;
  open: boolean;
  onClose: () => void;
  onSaved: (updated: RoomTemplate) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [templateName, setTemplateName] = useState("");
  const [state, setState] = useState<CreateRoomModalState>(BLANK_MODAL_STATE);
  // Deadline is held separately from `state.deadlineLocal` here because the
  // edit-template flow stores it as relative (time + offset), not absolute.
  // The state's deadlineLocal field is unused in this modal.
  const [deadline, setDeadline] = useState<RoomTemplatePayload["deadline"]>(DEFAULT_DEADLINE);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

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

  // Load the template into local state whenever the modal opens with a
  // (different) template.
  useEffect(() => {
    if (!open || !template) return;
    setTemplateName(template.name);
    setState(applyTemplateToModal(template.payload, new Date()));
    setDeadline(template.payload.deadline ?? DEFAULT_DEADLINE);
    setError("");
    setSaving(false);
  }, [open, template]);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!template || saving) return;
    const trimmedName = templateName.trim();
    if (!trimmedName) {
      setError("Template name is required.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      // Pass the relative deadline directly so captureTemplateFromModal
      // doesn't try to derive an offset from state.deadlineLocal (which
      // is unused in this modal).
      const payload = captureTemplateFromModal(state, new Date(), deadline);
      const updated = await updateRoomTemplate(template.id, {
        name: trimmedName,
        payload,
      });
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  const deadlineSection = (
    <section className="settings-section">
      <h3>Auto-close deadline</h3>
      <p className="settings-hint">
        Templates store the deadline as a time-of-day plus a day-offset
        relative to when the room is created. <strong>+0 days</strong>
        means today (rolling forward to tomorrow if the time has already
        passed). <strong>+1 day</strong> means tomorrow at this time.
        Hosts can still tweak the absolute datetime in the Create-room
        modal before clicking Create.
      </p>
      <div className="settings-controls">
        <label className="settings-toggle">
          <input
            type="checkbox"
            checked={deadline.enabled}
            onChange={(e) => setDeadline(d => ({ ...d, enabled: e.target.checked }))}
          />
          <span>Set an auto-close deadline</span>
        </label>
      </div>
      <div
        className="settings-controls"
        style={{
          opacity: deadline.enabled ? 1 : 0.55,
          pointerEvents: deadline.enabled ? "auto" : "none",
          marginTop: "0.4rem",
        }}
      >
        <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <span>Time:</span>
          <input
            type="time"
            value={deadline.time_of_day}
            onChange={(e) => setDeadline(d => ({
              ...d,
              time_of_day: e.target.value || "19:00",
            }))}
            disabled={!deadline.enabled}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <span>Days from now:</span>
          <input
            type="number"
            min={0}
            max={30}
            step={1}
            value={deadline.day_offset}
            onChange={(e) => setDeadline(d => ({
              ...d,
              day_offset: Math.max(0, Math.min(30, parseInt(e.target.value || "0", 10) || 0)),
            }))}
            disabled={!deadline.enabled}
            style={{ width: "5rem" }}
          />
        </label>
      </div>
    </section>
  );

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal">
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Edit template</strong>
          {template && (
            <span className="settings-modal-meta">{template.name}</span>
          )}
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <form onSubmit={handleSubmit} style={{ display: "contents" }}>
        <div className="settings-modal-body">
          <section className="settings-section">
            <h3>Template name</h3>
            <p className="settings-hint">
              How this template appears in the dropdown on the Create-room
              modal. Doesn't affect the room name itself — that's the field
              in <em>Room basics</em> below.
            </p>
            <div className="settings-controls">
              <input
                type="text"
                placeholder="Template label (e.g. Weekly async)"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                maxLength={80}
                required
              />
            </div>
          </section>

          <RoomTemplateFields
            state={state}
            setState={setState}
            basicsHint={
              "The room-name field below is the PRE-FILL applied when this template is used. " +
              "Leave it blank to have the host type a fresh name each time, or set a default like " +
              "\"Weekly async\" for a recurring shape."
            }
            nameRequired={false}
            namePlaceholder="Default room name (optional)"
            customDeadlineSection={deadlineSection}
          />

          {error && (
            <p className="settings-error" style={{ margin: 0 }}>{error}</p>
          )}
        </div>

        <footer className="settings-modal-footer">
          <button type="button" className="btn btn-sm" onClick={onClose}>Cancel</button>
          <button
            type="submit"
            className="btn btn-sm btn-primary"
            disabled={saving || !templateName.trim()}
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
        </footer>
      </form>
    </dialog>
  );
}
