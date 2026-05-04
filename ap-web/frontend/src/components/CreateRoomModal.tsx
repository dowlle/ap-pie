import { useEffect, useRef, useState } from "react";
import { createRoom } from "../api";
import { useAuth } from "../context/AuthContext";
import { localInputValueToIso } from "../lib/roomDeadline";

/**
 * Native <dialog> create-room modal. Same lifecycle pattern as
 * RoomSettingsModal / YamlModal: showModal() once on mount, ESC-to-cancel
 * via the cancel event, backdrop click closes via the click-target check.
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

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [requireDiscordLogin, setRequireDiscordLogin] = useState(false);
  const [deadlineLocal, setDeadlineLocal] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const hostName = user?.discord_username ?? "";

  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

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

  // Reset fields whenever the modal is reopened so a previous attempt's
  // state never leaks into a fresh creation.
  useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setRequireDiscordLogin(false);
      setDeadlineLocal("");
      setError("");
      setSubmitting(false);
    }
  }, [open]);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
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
        description,
        require_discord_login: requireDiscordLogin,
        submit_deadline: localInputValueToIso(deadlineLocal),
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal">
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Create room</strong>
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <form onSubmit={handleSubmit} className="settings-modal-body create-room-form">
        <input
          placeholder="Room name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
        />
        {hostName && (
          <p className="muted" style={{ margin: "0.25rem 0" }}>
            Hosting as <strong>{hostName}</strong>
          </p>
        )}
        <textarea
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
        <div className="form-row">
          <label title="Players must log in with Discord before they can submit a YAML to this room. Lets you see who uploaded what.">
            <input
              type="checkbox"
              checked={requireDiscordLogin}
              onChange={(e) => setRequireDiscordLogin(e.target.checked)}
            />
            Require Discord login
          </label>
        </div>
        <div className="form-row">
          <label title="Optional. The room auto-closes at this date/time in your local timezone. You can still close it manually before then.">
            Auto-close at:
            <input
              type="datetime-local"
              value={deadlineLocal}
              onChange={(e) => setDeadlineLocal(e.target.value)}
              style={{ marginLeft: "0.5rem" }}
            />
          </label>
          {deadlineLocal && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setDeadlineLocal("")}
              title="Clear the auto-close deadline"
            >
              Clear
            </button>
          )}
        </div>
        <div className="form-row">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!hostName || !name.trim() || submitting}
          >
            {submitting ? "Creating..." : "Create"}
          </button>
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
        </div>
        {error && <span className="upload-error">{error}</span>}
      </form>
    </dialog>
  );
}
