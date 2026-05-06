import { type Dispatch, type SetStateAction, useState } from "react";
import type { CreateRoomModalState } from "../lib/roomTemplates";
import MarkdownText from "./MarkdownText";

/**
 * FEAT-33: shared form-field rendering for the per-room shape.
 *
 * Used by both <CreateRoomModal> (for creating a room) and
 * <EditTemplateModal> (for editing a saved template). The two modals
 * differ only in their wrapping chrome and submit actions; every field
 * inside the body is the same shape.
 *
 * Room-name field copy varies by context, hence the nameLabel + nameHint
 * props. In Create, the hint mentions the field is required. In Edit,
 * the hint clarifies that it's the pre-fill when the template applies.
 */

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <h3>{title}</h3>
      <p className="settings-hint">{hint}</p>
    </>
  );
}

interface Props {
  state: CreateRoomModalState;
  setState: Dispatch<SetStateAction<CreateRoomModalState>>;
  /** Override the "Room basics" section's hint copy. Defaults to the
   *  create-room copy. */
  basicsHint?: string;
  /** Whether the room-name input is required. Create-room requires it;
   *  Edit-template doesn't (an empty pre-fill is valid). */
  nameRequired?: boolean;
  /** Placeholder shown inside the room-name input. */
  namePlaceholder?: string;
  /** Whether to autofocus the room-name input. Defaults to false; the
   *  Create modal sets this true so the host can type immediately. */
  autoFocusName?: boolean;
}

export default function RoomTemplateFields({
  state,
  setState,
  basicsHint,
  nameRequired = false,
  namePlaceholder = "Room name",
  autoFocusName = false,
}: Props) {
  const [descPreview, setDescPreview] = useState(false);

  const hint = basicsHint ?? (
    "The name shows up in the rooms list and on the public room page. " +
    "Description is optional and rendered above the YAML list for context."
  );

  return (
    <>
      <section className="settings-section">
        <SectionHeader title="Room basics" hint={hint} />
        <div className="settings-controls">
          <input
            type="text"
            placeholder={namePlaceholder}
            value={state.name}
            onChange={(e) => setState(s => ({ ...s, name: e.target.value }))}
            autoFocus={autoFocusName}
            required={nameRequired}
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
              name="room-template-apworld-policy"
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
              name="room-template-apworld-policy"
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
              name="room-template-apworld-policy"
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
    </>
  );
}
