import { useEffect, useRef, useState } from "react";
import {
  updateRoomTemplate,
  type RoomTemplate,
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
 * Important: the body's room-name field here represents the PRE-FILL the
 * template will apply when used in CreateRoomModal, NOT the actual room
 * name. Hint copy in the field section reflects that. Empty pre-fill is
 * valid and means "let the host type it themselves at create time."
 */
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
  // (different) template. We treat `now` as Date.now() so the deadline's
  // time-of-day + day-offset round-trip lands on a sensible absolute
  // datetime that the host can sanity-check before saving.
  useEffect(() => {
    if (!open || !template) return;
    setTemplateName(template.name);
    setState(applyTemplateToModal(template.payload, new Date()));
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
      const payload = captureTemplateFromModal(state, new Date());
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
