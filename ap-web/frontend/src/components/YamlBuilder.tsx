import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { BuilderSchemaEntry, TemplateOption } from "../api";
import { buildYamlContent, downloadYaml } from "../lib/yamlBuild";
import { highlightYaml } from "../lib/yamlHighlight";

/**
 * FEAT-38: guided YAML builder modal. One shared shell for all three
 * mounts - RoomPublic (players), RoomDetail (hosts) and /apworlds (the
 * room-less "Create YAML" flow).
 *
 * Two steps: an options form auto-rendered from the Tier-1 builder schema
 * (grouped by the apworld's own option_groups), then a review step showing
 * the emitted YAML (js-yaml, so quoting is always valid) with Download
 * always available and a caller-supplied submit action / extra actions.
 *
 * The caller decides which games are offered (`games` should be tier >= 1,
 * i.e. schema !== null) and what "submit" means for its context:
 * RoomPublic wires submitYamlContentToRoom (public gates apply), RoomDetail
 * wires the host create endpoint, /apworlds supplies reviewExtra room
 * actions instead.
 */
export default function YamlBuilder({
  open,
  games,
  initialGame,
  submit,
  reviewExtra,
  onClose,
}: {
  open: boolean;
  games: BuilderSchemaEntry[];
  /** apworld_name of the game to preselect. With exactly one game the
   *  picker row is hidden entirely. */
  initialGame?: string;
  submit?: {
    label: string;
    /** Perform the submission; resolve to a user-facing success message. */
    run: (yamlContent: string, playerName: string, game: string) => Promise<string>;
  };
  /** Rendered in the review step above the footer - the /apworlds flow
   *  injects its "Add to room / Create room" actions here. */
  reviewExtra?: (yamlContent: string, playerName: string) => ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  const [selected, setSelected] = useState<string>("");
  const [playerName, setPlayerName] = useState("Player1");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [step, setStep] = useState<"form" | "review">("form");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const entry = useMemo(
    () => games.find((g) => g.apworld_name === selected) ?? null,
    [games, selected],
  );

  // Native <dialog> lifecycle - same pattern as CreateRoomModal.
  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    else if (!open && dlg.open) dlg.close();
    const onCancel = (e: Event) => { e.preventDefault(); onCloseRef.current(); };
    dlg.addEventListener("cancel", onCancel);
    return () => dlg.removeEventListener("cancel", onCancel);
  }, [open]);

  // Reset on open; preselect the requested (or only) game.
  useEffect(() => {
    if (!open) return;
    const first =
      (initialGame && games.some((g) => g.apworld_name === initialGame))
        ? initialGame
        : games.length === 1
        ? games[0].apworld_name
        : "";
    setSelected(first);
    setStep("form");
    setBusy(false);
    setError("");
    setSuccess("");
  }, [open, initialGame, games]);

  // Seed form values from schema defaults whenever the game changes.
  useEffect(() => {
    if (!entry?.schema) { setValues({}); return; }
    const defaults: Record<string, unknown> = {};
    for (const opt of entry.schema.options) defaults[opt.name] = opt.default;
    setValues(defaults);
    setStep("form");
    setError("");
    setSuccess("");
  }, [entry]);

  const yamlContent = useMemo(() => {
    if (!entry?.schema || step !== "review") return "";
    return buildYamlContent({
      playerName: playerName.trim() || "Player1",
      game: entry.game,
      worldVersion: entry.version,
      template: entry.schema,
      values,
    });
  }, [entry, step, playerName, values]);

  const handleSubmit = async () => {
    if (!submit || !yamlContent || !entry) return;
    setBusy(true);
    setError("");
    try {
      const msg = await submit.run(yamlContent, playerName.trim() || "Player1", entry.game);
      setSuccess(msg);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  };

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  const schema = entry?.schema ?? null;

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal yaml-builder-modal">
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Build your YAML</strong>
          {entry && (
            <span className="settings-modal-meta">
              {entry.display_name} · v{entry.version}
            </span>
          )}
        </div>
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      <div className="settings-modal-body">
        {step === "form" && (
          <>
            <section className="settings-section">
              <h3>Player</h3>
              <div className="settings-controls yaml-builder-toprow">
                {games.length > 1 && (
                  <label className="yaml-builder-field">
                    <span>Game</span>
                    <select
                      value={selected}
                      onChange={(e) => setSelected(e.target.value)}
                    >
                      <option value="">Select a game…</option>
                      {games.map((g) => (
                        <option key={g.apworld_name} value={g.apworld_name}>
                          {g.display_name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="yaml-builder-field">
                  <span>Player name</span>
                  <input
                    type="text"
                    value={playerName}
                    onChange={(e) => setPlayerName(e.target.value)}
                    maxLength={16}
                    placeholder="Your slot name (max 16 chars)"
                  />
                </label>
              </div>
              <p className="settings-hint">
                This becomes your slot name in the multiworld. Every option
                below starts at the game's default - you only need to change
                what you care about.
              </p>
            </section>

            {schema && schema.options.length > 0 && (
              <OptionsForm schema={schema} values={values} setValues={setValues} />
            )}
          </>
        )}

        {step === "review" && entry && (
          <>
            <section className="settings-section">
              <h3>Review</h3>
              <p className="settings-hint">
                This is the YAML that will be {submit ? "submitted" : "downloaded"}.
                The version pin (v{entry.version}) matches what this{" "}
                {submit ? "room runs" : "builder was opened for"}, so it
                validates without version-mismatch warnings.
              </p>
              <pre className="yaml-builder-preview">{highlightYaml(yamlContent)}</pre>
            </section>
            {reviewExtra && !success && reviewExtra(yamlContent, playerName.trim() || "Player1")}
          </>
        )}

        {error && <p className="settings-error" style={{ margin: 0 }}>{error}</p>}
        {success && (
          <p className="settings-aux-note" style={{ margin: 0, color: "var(--green)" }}>
            ✓ {success}
          </p>
        )}
      </div>

      <footer className="settings-modal-footer">
        {step === "form" && (
          <>
            <button type="button" className="btn btn-sm" onClick={onClose}>Cancel</button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={!schema || !playerName.trim()}
              onClick={() => { setError(""); setStep("review"); }}
            >
              Review YAML →
            </button>
          </>
        )}
        {step === "review" && entry && (
          <>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => { setError(""); setSuccess(""); setStep("form"); }}
              disabled={busy}
            >
              ← Back
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => downloadYaml(yamlContent, playerName.trim() || "Player1", entry.game)}
              disabled={busy}
            >
              Download .yaml
            </button>
            {submit && !success && (
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={handleSubmit}
                disabled={busy}
              >
                {busy ? "Submitting…" : submit.label}
              </button>
            )}
            {success && (
              <button type="button" className="btn btn-sm btn-primary" onClick={onClose}>
                Done
              </button>
            )}
          </>
        )}
      </footer>
    </dialog>
  );
}

/** Options grouped by category, each group a collapsible section. */
function OptionsForm({
  schema,
  values,
  setValues,
}: {
  schema: NonNullable<BuilderSchemaEntry["schema"]>;
  values: Record<string, unknown>;
  setValues: React.Dispatch<React.SetStateAction<Record<string, unknown>>>;
}) {
  return (
    <>
      {schema.categories.map((cat) => {
        const opts = schema.options.filter((o) => o.category === cat);
        if (opts.length === 0) return null;
        return (
          <details key={cat} className="settings-section yaml-builder-group" open>
            <summary>
              {cat} <span className="muted">({opts.length})</span>
            </summary>
            <div className="yaml-builder-group-body">
              {opts.map((opt) => (
                <div key={opt.name} className="yaml-builder-option">
                  <div className="yaml-builder-option-header">
                    <span className="yaml-builder-option-name">
                      {opt.display_name || opt.name}
                    </span>
                    <code className="yaml-builder-option-key">{opt.name}</code>
                  </div>
                  {opt.description && (
                    <p className="yaml-builder-option-desc">{opt.description}</p>
                  )}
                  <OptionControl
                    option={opt}
                    value={values[opt.name]}
                    onChange={(v) => setValues((prev) => ({ ...prev, [opt.name]: v }))}
                  />
                </div>
              ))}
            </div>
          </details>
        );
      })}
    </>
  );
}

/** One form control per option type. */
function OptionControl({
  option,
  value,
  onChange,
}: {
  option: TemplateOption;
  value: unknown;
  onChange: (val: unknown) => void;
}) {
  switch (option.type) {
    case "toggle":
      return (
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>{value ? "on" : "off"}</span>
        </label>
      );

    case "choice":
      return (
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          {option.choices?.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      );

    case "range": {
      const named = option.named_values;
      const num = typeof value === "number" ? value : Number(value ?? option.default);
      const matchingAlias = named
        ? Object.entries(named).find(([, v]) => v === num)?.[0]
        : undefined;
      return (
        <div className="range-input">
          <input
            type="number"
            min={option.min}
            max={option.max}
            value={Number.isFinite(num) ? num : ""}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <input
            type="range"
            min={option.min}
            max={option.max}
            value={Number.isFinite(num) ? num : option.min}
            onChange={(e) => onChange(Number(e.target.value))}
            className="range-slider"
          />
          {named && Object.keys(named).length > 0 && (
            <select
              value={matchingAlias ?? ""}
              onChange={(e) => {
                if (e.target.value && named[e.target.value] !== undefined) {
                  onChange(named[e.target.value]);
                }
              }}
            >
              <option value="">Custom</option>
              {Object.entries(named).map(([name, n]) => (
                <option key={name} value={name}>{name} ({n})</option>
              ))}
            </select>
          )}
        </div>
      );
    }

    case "list": {
      // With known valid keys, render a checkbox grid (e.g. pokepelago's
      // region picker). Free-form lists fall back to a comma textarea.
      const arr = Array.isArray(value) ? (value as string[]) : [];
      if (option.choices && option.choices.length > 0) {
        return (
          <div className="yaml-builder-checkgrid">
            {option.choices.map((c) => (
              <label key={c} className="yaml-builder-check">
                <input
                  type="checkbox"
                  checked={arr.includes(c)}
                  onChange={(e) =>
                    onChange(
                      e.target.checked
                        ? [...arr, c]
                        : arr.filter((x) => x !== c),
                    )
                  }
                />
                <span>{c}</span>
              </label>
            ))}
          </div>
        );
      }
      return (
        <textarea
          value={Array.isArray(value) ? arr.join(", ") : String(value ?? "")}
          onChange={(e) => {
            const text = e.target.value;
            onChange(text ? text.split(",").map((s) => s.trim()).filter(Boolean) : []);
          }}
          placeholder="Comma-separated values (leave empty for default)"
          rows={2}
        />
      );
    }

    case "dict": {
      // With known keys (OptionCounter - trap/filler weights), render one
      // number row per key. Unknown-key dicts fall back to a textarea.
      const dictVal = (typeof value === "object" && value !== null)
        ? (value as Record<string, unknown>)
        : {};
      const keys = option.valid_keys?.length
        ? option.valid_keys
        : Object.keys(dictVal);
      const allNumeric = keys.length > 0 && keys.every(
        (k) => dictVal[k] === undefined || typeof dictVal[k] === "number",
      );
      if (allNumeric && keys.length > 0 && typeof value !== "string") {
        return (
          <div className="yaml-builder-counter">
            {keys.map((k) => (
              <label key={k} className="yaml-builder-counter-row">
                <code>{k}</code>
                <input
                  type="number"
                  min={0}
                  value={typeof dictVal[k] === "number" ? (dictVal[k] as number) : 0}
                  onChange={(e) =>
                    onChange({ ...dictVal, [k]: Number(e.target.value) })
                  }
                />
              </label>
            ))}
          </div>
        );
      }
      return (
        <textarea
          value={
            typeof value === "string"
              ? value
              : Object.entries(dictVal).map(([k, v]) => `${k}: ${v}`).join("\n")
          }
          onChange={(e) => onChange(e.target.value)}
          placeholder="key: value (one per line)"
          rows={3}
        />
      );
    }

    default:
      return (
        <input
          type="text"
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}
