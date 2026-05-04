import { useEffect, useRef, useState } from "react";
import { createRoom } from "../api";
import { useAuth } from "../context/AuthContext";
import { localInputValueToIso } from "../lib/roomDeadline";

/**
 * Native <dialog> create-room modal. Same lifecycle and visual chrome as
 * RoomSettingsModal: showModal once on mount, ESC-to-cancel via the cancel
 * event, backdrop click closes via target check, sectioned cards in the
 * body, primary action in the sticky footer.
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

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [requireDiscordLogin, setRequireDiscordLogin] = useState(false);
  const [deadlineLocal, setDeadlineLocal] = useState("");
  // APWorld version policy mirrors the radio in RoomSettingsModal so hosts
  // pick the right shape at create time instead of having to jump back into
  // Settings afterwards. "strict" is the default and matches the column
  // defaults (allow_mixed=false, force_latest=false).
  const [policyMode, setPolicyMode] = useState<"strict" | "flexible" | "latest">("strict");
  const [autoUpgrade, setAutoUpgrade] = useState(true);
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
      setPolicyMode("strict");
      setAutoUpgrade(true);
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
        // Send both display flags atomically so the radio's invariants
        // (exactly one of strict / flexible / latest) hold server-side.
        allow_mixed_apworld_versions: policyMode === "flexible",
        force_latest_apworld_versions: policyMode === "latest",
        auto_upgrade_apworld_pins: autoUpgrade,
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
              <textarea
                placeholder="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                style={{
                  flex: 1,
                  minWidth: "12rem",
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
                  checked={requireDiscordLogin}
                  onChange={(e) => setRequireDiscordLogin(e.target.checked)}
                />
                <span>Login required</span>
              </label>
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
                value={deadlineLocal}
                onChange={(e) => setDeadlineLocal(e.target.value)}
              />
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
                  checked={policyMode === "strict"}
                  onChange={() => setPolicyMode("strict")}
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
                  checked={policyMode === "flexible"}
                  onChange={() => setPolicyMode("flexible")}
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
                  checked={policyMode === "latest"}
                  onChange={() => setPolicyMode("latest")}
                />
                <span>
                  <strong>Always use the newest version</strong>: ignores per-game pins, always tells
                  players to install whatever's currently latest in the index.
                </span>
              </label>
            </div>

            <div className="settings-controls" style={{ marginTop: "0.6rem" }}>
              <label className="settings-toggle" style={{ opacity: policyMode === "latest" ? 0.55 : 1 }}>
                <input
                  type="checkbox"
                  checked={autoUpgrade}
                  disabled={policyMode === "latest"}
                  onChange={(e) => setAutoUpgrade(e.target.checked)}
                />
                <span>Auto-upgrade pins to newest YAML version</span>
              </label>
            </div>
            <p className="settings-aux-note">
              On by default. When a YAML uploads with a `requires.game.&lt;Name&gt;` version higher
              than the current pin, the pin bumps up to match.
              {policyMode === "latest" && (
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
        </div>

        <footer className="settings-modal-footer">
          <button type="button" className="btn btn-sm" onClick={onClose}>Cancel</button>
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
