import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { BuilderSchemaEntry, Preset, TemplateOption } from "../api";
import { createPreset, getPresets, recordPresetUse, saveMyYaml } from "../api";
import { dump, load } from "js-yaml";
import { buildYamlContent, downloadYaml, isRandomValue } from "../lib/yamlBuild";
import { CORE_CATEGORY, CORE_OPTIONS } from "../lib/coreOptions";
import { importYaml } from "../lib/yamlImport";
import { highlightYaml } from "../lib/yamlHighlight";
import MarkdownText from "./MarkdownText";
import { trackBuilderAbandoned, trackBuilderEmitted, trackBuilderOpened } from "../lib/analytics";

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
  surface = "unknown",
  roomId,
  initialYaml,
  initialValues,
  initialPlayerName,
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
  /** FEAT-31: which mount opened the builder - "room_public", "room_detail"
   *  or "apworlds". Recorded as a plain label so builder usage can be split
   *  by entry point. */
  surface?: string;
  /** Room the builder is operating in, when there is one. */
  roomId?: string;
  /** FEAT-43: open with an existing YAML loaded. Values the schema knows
   *  fill the form; anything else sends the document to the editor instead,
   *  because a form that silently dropped a plando block would be worse
   *  than no form at all. */
  initialYaml?: string | null;
  /** FEAT-43: open with a saved configuration loaded into the form. Used by
   *  "Open in builder" for a config-kind library entry, where there is no
   *  document to parse - the values were never a file in the first place. */
  initialValues?: Record<string, unknown> | null;
  initialPlayerName?: string | null;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  const [selected, setSelected] = useState<string>("");
  const [playerName, setPlayerName] = useState("Player1");
  const [values, setValues] = useState<Record<string, unknown>>({});
  // Archipelago-level options. Absent key = "leave the game default".
  const [coreValues, setCoreValues] = useState<Record<string, unknown>>({});
  const [step, setStep] = useState<"form" | "review">("form");
  // Non-null once the review step's YAML has been hand-edited.
  const [manualYaml, setManualYaml] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // FEAT-42: presets for the selected game. Published ones plus the
  // viewer's own drafts; the endpoint decides which.
  const [presets, setPresets] = useState<Preset[]>([]);
  const [savingPreset, setSavingPreset] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [presetFilter, setPresetFilter] = useState("");
  const [showAllPresets, setShowAllPresets] = useState(false);
  const [presetSaved, setPresetSaved] = useState("");

  const entry = useMemo(
    () => games.find((g) => g.apworld_name === selected) ?? null,
    [games, selected],
  );

  // FEAT-31 builder funnel. `emitted` marks that the visitor got a YAML out
  // of the builder (downloaded or submitted); anything else is an abandon,
  // recorded with the step they were on. Refs, not state: these must be
  // readable from the unload path without re-rendering.
  const emittedRef = useRef(false);
  const abandonReportedRef = useRef(false);
  const stepRef = useRef(step);
  useEffect(() => { stepRef.current = step; }, [step]);
  const openedKeyRef = useRef("");

  const noteEmitted = (action: string) => {
    if (!entry) return;
    emittedRef.current = true;
    trackBuilderEmitted(entry.game, entry.version, action, roomId, manualYaml !== null);
  };

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
    setManualYaml(null);
    setEditing(false);
    setCoreValues({});
    setPresets([]);
    setPresetFilter("");
    setShowAllPresets(false);
    setSavingPreset(false);
    setPresetName("");
    setPresetSaved("");
  }, [open, initialGame, games]);

  // FEAT-31: one "opened" per (open, game) pair - switching game inside an
  // open builder counts as opening the builder for that game, reopening the
  // same game after a close counts again.
  useEffect(() => {
    if (!open || !entry) return;
    const key = `${entry.apworld_name}@${entry.version}`;
    if (openedKeyRef.current === key) return;
    openedKeyRef.current = key;
    emittedRef.current = false;
    abandonReportedRef.current = false;
    trackBuilderOpened(entry.game, entry.version, surface, roomId);
  }, [open, entry, surface, roomId]);

  // Abandonment: fired when the builder closes (or the tab goes away) after
  // being opened for a game without producing a YAML.
  useEffect(() => {
    if (open) return;
    openedKeyRef.current = "";
  }, [open]);

  useEffect(() => {
    if (!open || !entry) return;
    const abandonIfUnfinished = (unloading: boolean) => {
      if (emittedRef.current || abandonReportedRef.current) return;
      // Only latch when the send actually succeeded. Latching first meant a
      // dropped send permanently suppressed the report for this builder.
      abandonReportedRef.current = trackBuilderAbandoned(
        entry.game, entry.version, stepRef.current, roomId, unloading,
      );
    };
    const onPageHide = () => abandonIfUnfinished(true);
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      abandonIfUnfinished(false);
    };
  }, [open, entry, roomId]);

  // FEAT-43: import an existing document when one is handed in. Runs after
  // the defaults effect below has seeded the form, so imported values land
  // on top of defaults rather than under them.
  const importedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!open || !entry?.schema || !initialYaml) return;
    if (importedRef.current === initialYaml) return;
    importedRef.current = initialYaml;
    const parsed = importYaml(initialYaml, entry.schema);
    if (!parsed) {
      // Unparseable: hand it to the editor rather than refusing to open.
      setManualYaml(initialYaml);
      setStep("review");
      return;
    }
    if (parsed.unknown.length > 0 || parsed.extraRootKeys.length > 0) {
      // Carries things no form can represent (plando, triggers, options this
      // version dropped). Editing it as text is the honest answer.
      setManualYaml(initialYaml);
      setStep("review");
      setError(
        `Opened in the editor: this YAML carries ${
          [...parsed.unknown, ...parsed.extraRootKeys].slice(0, 3).join(", ")
        }${
          parsed.unknown.length + parsed.extraRootKeys.length > 3 ? " and more" : ""
        }, which the form cannot show without dropping it.`,
      );
      return;
    }
    if (parsed.playerName) setPlayerName(parsed.playerName);
    setValues((prev) => ({ ...prev, ...parsed.values }));
    setCoreValues((prev) => ({ ...prev, ...parsed.coreValues }));
    setStep("form");
  }, [open, entry, initialYaml]);

  // FEAT-43: a saved configuration, applied the same way a preset is.
  const importedValuesRef = useRef<Record<string, unknown> | null>(null);
  useEffect(() => {
    if (!open || !entry?.schema || !initialValues) return;
    if (importedValuesRef.current === initialValues) return;
    importedValuesRef.current = initialValues;
    const core: Record<string, unknown> = {};
    const game: Record<string, unknown> = {};
    const coreNames = new Set(CORE_OPTIONS.map((o) => o.name));
    for (const [k, v] of Object.entries(initialValues)) {
      if (coreNames.has(k)) core[k] = v;
      else game[k] = v;
    }
    setCoreValues((prev) => ({ ...prev, ...core }));
    setValues((prev) => ({ ...prev, ...game }));
    if (initialPlayerName) setPlayerName(initialPlayerName);
  }, [open, entry, initialValues, initialPlayerName]);

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

  // FEAT-42: load presets for whatever game is selected. Failure is silent:
  // presets are an aid, and a builder that still works without them is
  // better than an error banner over a form that is fine.
  useEffect(() => {
    if (!open || !entry) { setPresets([]); return; }
    let cancelled = false;
    getPresets(entry.apworld_name, entry.version)
      .then((list) => { if (!cancelled) setPresets(list); })
      .catch(() => { if (!cancelled) setPresets([]); });
    return () => { cancelled = true; };
  }, [open, entry]);

  // Presets are ordered server-side (official, then upvotes, then uses), so
  // the first few are the ones worth showing. A game with fifty presets
  // would otherwise bury the actual options form under a wall of cards.
  const filteredPresets = useMemo(() => {
    const q = presetFilter.trim().toLowerCase();
    if (!q) return presets;
    return presets.filter((p) =>
      `${p.name} ${p.description} ${p.author_username ?? ""}`.toLowerCase().includes(q),
    );
  }, [presets, presetFilter]);

  const shownPresets = showAllPresets
    ? filteredPresets
    : filteredPresets.slice(0, PRESET_PREVIEW_COUNT);
  const hiddenPresetCount = showAllPresets
    ? 0
    : Math.max(0, filteredPresets.length - PRESET_PREVIEW_COUNT);

  const CORE_KEYS = useMemo(() => new Set(CORE_OPTIONS.map((o) => o.name)), []);

  /** Apply a preset. Simple presets fill the form and leave everything
   *  editable; advanced ones carry constructs no form can express, so they
   *  load straight into the review step's editor with the player's own slot
   *  name substituted for the author's. */
  const applyPreset = (p: Preset) => {
    setError("");
    setSuccess("");
    if (p.kind === "advanced" && p.yaml_content) {
      let text = p.yaml_content;
      try {
        const doc = load(text) as Record<string, unknown>;
        if (doc && typeof doc === "object") {
          doc.name = playerName.trim() || "Player1";
          text = dump(doc, { noRefs: true, lineWidth: -1, sortKeys: false });
        }
      } catch {
        // Unparseable stored YAML: hand it over as-is rather than refusing.
        // The author will see the same text they saved, and the server
        // validates on submit.
      }
      setManualYaml(text);
      setEditing(false);
      setStep("review");
    } else {
      const applies = (p.applies ?? p.values ?? {}) as Record<string, unknown>;
      const core: Record<string, unknown> = {};
      const game: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(applies)) {
        if (CORE_KEYS.has(k)) core[k] = v;
        else game[k] = v;
      }
      setCoreValues((prev) => ({ ...prev, ...core }));
      setValues((prev) => ({ ...prev, ...game }));
      setManualYaml(null);
      setStep("form");
    }
    recordPresetUse(p.id);
  };

  /** FEAT-43: keep this YAML in your own library. Distinct from saving a
   *  preset: a library entry carries your slot name and is yours, a preset
   *  is a configuration you may publish for other people. */
  const handleSaveToLibrary = async () => {
    if (!entry) return;
    setBusy(true);
    setError("");
    try {
      await saveMyYaml({
        apworld_name: entry.apworld_name,
        version: entry.version,
        player_name: submittedIdentity.playerName,
        label: `${entry.display_name} - ${submittedIdentity.playerName}`,
        kind: manualYaml !== null ? "advanced" : "simple",
        ...(manualYaml !== null
          ? { yaml_content: manualYaml }
          : { values: { ...coreValues, ...values } }),
      });
      setPresetSaved("Saved to My stuff. You can reopen it in the builder any time.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  const handleSavePreset = async () => {
    if (!entry) return;
    const name = presetName.trim();
    if (!name) return;
    setBusy(true);
    setError("");
    try {
      const saved = await createPreset({
        apworld_name: entry.apworld_name,
        version: entry.version,
        name,
        kind: manualYaml !== null ? "advanced" : "simple",
        ...(manualYaml !== null
          ? { yaml_content: manualYaml }
          : { values: { ...coreValues, ...values } }),
      });
      setPresetSaved(
        `Saved "${saved.name}" to your presets. Publish it from My presets when you want others to see it.`,
      );
      setSavingPreset(false);
      setPresetName("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save preset");
    } finally {
      setBusy(false);
    }
  };

  const generatedYaml = useMemo(() => {
    if (!entry?.schema || step !== "review") return "";
    return buildYamlContent({
      playerName: playerName.trim() || "Player1",
      game: entry.game,
      worldVersion: entry.version,
      template: entry.schema,
      apVersion: entry.schema.ap_version,
      values,
      coreValues,
      coreOptions: CORE_OPTIONS,
    });
  }, [entry, step, playerName, values, coreValues]);

  // Hand-edited YAML wins over the generated document when present. The
  // builder only covers the options an apworld declares, so anything AP
  // supports centrally - progression_balancing, start_inventory, triggers,
  // multiple slots in one file - has to be reachable somehow, and until
  // those get real controls this is that path.
  const yamlContent = manualYaml ?? generatedYaml;

  /** Player name + game as they appear in the document being submitted.
   *  A hand-edit may have changed `name:`, and the room endpoints take the
   *  player name as its own field, so read it back rather than trusting
   *  the form. */
  const submittedIdentity = useMemo(() => {
    const fallback = {
      playerName: playerName.trim() || "Player1",
      game: entry?.game ?? "",
    };
    if (!manualYaml) return fallback;
    try {
      const doc = load(manualYaml) as Record<string, unknown> | undefined;
      if (!doc || typeof doc !== "object") return fallback;
      return {
        playerName: typeof doc.name === "string" && doc.name.trim() ? doc.name.trim() : fallback.playerName,
        game: typeof doc.game === "string" && doc.game.trim() ? doc.game.trim() : fallback.game,
      };
    } catch {
      // Invalid YAML: fall back to the form values. The server validates on
      // submit and will report the real parse error.
      return fallback;
    }
  }, [manualYaml, playerName, entry]);

  const handleSubmit = async () => {
    if (!submit || !yamlContent || !entry) return;
    setBusy(true);
    setError("");
    try {
      const msg = await submit.run(
        yamlContent, submittedIdentity.playerName, submittedIdentity.game,
      );
      setSuccess(msg);
      noteEmitted("submit");
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

            {schema && presets.length > 0 && (
              <details className="settings-section yaml-builder-group" open>
                <summary>
                  Start from a preset <span className="muted">({presets.length})</span>
                </summary>
                <div className="yaml-builder-group-body">
                <p className="settings-hint">
                  A configuration someone else already worked out. Applying one
                  fills the form below and changes nothing you cannot edit
                  afterwards.
                </p>
                {presets.length > PRESET_FILTER_THRESHOLD && (
                  <input
                    type="search"
                    className="preset-filter"
                    placeholder="Filter presets by name, description or author..."
                    value={presetFilter}
                    onChange={(e) => setPresetFilter(e.target.value)}
                  />
                )}
                <ul className="preset-list">
                  {shownPresets.map((p) => (
                    <li key={p.id} className="preset-row">
                      <div className="preset-row-text">
                        <div className="preset-row-head">
                          <strong>{p.name}</strong>
                          {p.is_official && <span className="badge badge-builtin">official</span>}
                          {p.kind === "advanced" && (
                            <span
                              className="badge badge-save"
                              title="Carries plando, triggers or item links. Opens in the YAML editor."
                            >
                              advanced
                            </span>
                          )}
                          {p.status === "private" && (
                            <span className="badge">draft</span>
                          )}
                        </div>
                        {p.description && <p className="preset-row-desc">{p.description}</p>}
                        <p className="preset-row-meta">
                          {p.author_username ? `by ${p.author_username}` : "by an unknown author"}
                          {" · "}
                          {p.uses === 1 ? "used once" : `used ${p.uses} times`}
                          {p.score > 0 && ` · ${p.score} upvote${p.score === 1 ? "" : "s"}`}
                          {p.version !== entry?.version && ` · written for v${p.version}`}
                          {p.stale_keys.length > 0 &&
                            ` · ${p.stale_keys.length} option${
                              p.stale_keys.length === 1 ? "" : "s"
                            } no longer apply`}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-sm preset-use-btn"
                        onClick={() => applyPreset(p)}
                      >
                        Use this
                      </button>
                    </li>
                  ))}
                </ul>
                {filteredPresets.length === 0 && (
                  <p className="settings-hint" style={{ margin: 0 }}>
                    No presets match that filter.
                  </p>
                )}
                {hiddenPresetCount > 0 && (
                  <button
                    type="button"
                    className="yaml-builder-desc-toggle"
                    onClick={() => setShowAllPresets(true)}
                  >
                    Show {hiddenPresetCount} more preset{hiddenPresetCount === 1 ? "" : "s"}
                  </button>
                )}
                {showAllPresets && filteredPresets.length > PRESET_PREVIEW_COUNT && (
                  <button
                    type="button"
                    className="yaml-builder-desc-toggle"
                    onClick={() => setShowAllPresets(false)}
                  >
                    Show fewer
                  </button>
                )}
                </div>
              </details>
            )}

            {schema && (
              <CoreOptionsForm values={coreValues} setValues={setCoreValues} />
            )}

            {schema && schema.options.length > 0 && (
              <OptionsForm schema={schema} values={values} setValues={setValues} />
            )}

            {schema && schema.options.length === 0 && (
              <section className="settings-section">
                <h3>Game options</h3>
                <p className="settings-hint" style={{ margin: 0 }}>
                  {entry?.display_name} defines no options of its own, so there
                  is nothing more to set here. The Archipelago options above
                  still apply, and the YAML this produces is complete and ready
                  to submit.
                </p>
              </section>
            )}
          </>
        )}

        {step === "review" && entry && (
          <>
            <section className="settings-section">
              <div className="yaml-builder-review-head">
                <h3>Review</h3>
                <div className="yaml-builder-review-actions">
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={handleSaveToLibrary}
                    title="Keep this YAML in your own library so you can reopen or reuse it"
                  >
                    Save to my YAMLs
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => { setSavingPreset((v) => !v); setPresetSaved(""); }}
                  >
                    Save as preset
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => {
                      if (!editing && manualYaml === null) setManualYaml(generatedYaml);
                      setEditing((v) => !v);
                    }}
                  >
                    {editing ? "Done editing" : "Edit YAML"}
                  </button>
                </div>
              </div>
              <p className="settings-hint">
                This is the YAML that will be {submit ? "submitted" : "downloaded"}.
                The version pin (v{entry.version}) matches what this{" "}
                {submit ? "room runs" : "builder was opened for"}, so it
                validates without version-mismatch warnings.
              </p>
              {savingPreset && (
                <div className="preset-save-row">
                  <input
                    type="text"
                    value={presetName}
                    maxLength={80}
                    placeholder="Name this preset, e.g. First multiworld, gentle"
                    onChange={(e) => setPresetName(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-sm btn-primary"
                    disabled={busy || !presetName.trim()}
                    onClick={handleSavePreset}
                  >
                    {busy ? "Saving…" : "Save"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setSavingPreset(false)}
                  >
                    Cancel
                  </button>
                </div>
              )}
              {presetSaved && (
                <p className="settings-aux-note" style={{ color: "var(--green)" }}>
                  ✓ {presetSaved}
                </p>
              )}
              {editing ? (
                <textarea
                  className="yaml-builder-editor"
                  value={yamlContent}
                  spellCheck={false}
                  onChange={(e) => setManualYaml(e.target.value)}
                  rows={18}
                />
              ) : (
                <pre className="yaml-builder-preview">{highlightYaml(yamlContent)}</pre>
              )}
              {manualYaml !== null && (
                <p className="settings-aux-note yaml-builder-manual-note">
                  Hand-edited. The options form no longer drives this document, so
                  anything the builder does not cover yet - Archipelago's own
                  options like <code>progression_balancing</code> or{" "}
                  <code>start_inventory</code>, or extra slots - can be written
                  here directly.{" "}
                  <button
                    type="button"
                    className="yaml-builder-desc-toggle"
                    onClick={() => { setManualYaml(null); setEditing(false); }}
                  >
                    Discard edits and rebuild from the form
                  </button>
                </p>
              )}
            </section>
            {reviewExtra && !success && reviewExtra(yamlContent, submittedIdentity.playerName)}
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
              onClick={() => { setError(""); setSuccess(""); setEditing(false); setStep("form"); }}
              disabled={busy}
              title={
                manualYaml !== null
                  ? "Your hand-edits are kept; changing the form again will not overwrite them until you discard them"
                  : undefined
              }
            >
              ← Back
            </button>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                downloadYaml(
                  yamlContent, submittedIdentity.playerName, submittedIdentity.game,
                );
                noteEmitted("download");
              }}
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
/**
 * Archipelago's own options, above the game's own.
 *
 * Every control starts on "game default" and is only written into the YAML
 * once the user picks something - see lib/coreOptions for why writing our
 * own defaults would be wrong. The footer note points at the review step's
 * editor for the parts of Archipelago's option surface that deliberately
 * have no form here.
 */
function CoreOptionsForm({
  values,
  setValues,
}: {
  values: Record<string, unknown>;
  setValues: React.Dispatch<React.SetStateAction<Record<string, unknown>>>;
}) {
  return (
    <details className="settings-section yaml-builder-group" open>
      <summary>
        {CORE_CATEGORY} <span className="muted">({CORE_OPTIONS.length})</span>
      </summary>
      <div className="yaml-builder-group-body">
        {CORE_OPTIONS.map((opt) => {
          const set = values[opt.name] !== undefined && values[opt.name] !== "";
          return (
            <div key={opt.name} className="yaml-builder-option">
              <div className="yaml-builder-option-text">
                <div className="yaml-builder-option-header">
                  <span className="yaml-builder-option-name">{opt.display_name}</span>
                  <code className="yaml-builder-option-key">{opt.name}</code>
                </div>
                <OptionDescription text={opt.description} />
              </div>
              <div className="yaml-builder-option-control">
                {set ? (
                  <>
                    <OptionControl
                      option={opt}
                      value={values[opt.name]}
                      onChange={(v) => setValues((prev) => ({ ...prev, [opt.name]: v }))}
                    />
                    <button
                      type="button"
                      className="yaml-builder-desc-toggle"
                      onClick={() =>
                        setValues((prev) => {
                          const next = { ...prev };
                          delete next[opt.name];
                          return next;
                        })
                      }
                    >
                      Use the game's default
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="btn btn-sm yaml-builder-core-set"
                    onClick={() =>
                      setValues((prev) => ({ ...prev, [opt.name]: opt.default }))
                    }
                  >
                    Game default · change
                  </button>
                )}
              </div>
            </div>
          );
        })}
        <p className="settings-hint yaml-builder-advanced-note">
          Archipelago supports more per-slot settings than this form covers:
          starting inventory, excluded and priority locations, item links,
          plando and triggers. Those need exact item and location names, so
          they are not offered as fields. Use <strong>Edit YAML</strong> in the
          next step to add them by hand.
        </p>
      </div>
    </details>
  );
}

function OptionsForm({
  schema,
  values,
  setValues,
}: {
  schema: NonNullable<BuilderSchemaEntry["schema"]>;
  values: Record<string, unknown>;
  setValues: React.Dispatch<React.SetStateAction<Record<string, unknown>>>;
}) {
  // Gap 4: CTR has 26 options and Stardew has 53. Past a certain size the
  // only way to change one thing is to hunt for it, so the form gets a
  // filter. It appears only when there are enough options to need it.
  const [filter, setFilter] = useState("");
  const q = filter.trim().toLowerCase();
  const matches = (o: TemplateOption) =>
    !q ||
    o.name.toLowerCase().includes(q) ||
    (o.display_name ?? "").toLowerCase().includes(q) ||
    (o.description ?? "").toLowerCase().includes(q);
  const hitCount = q ? schema.options.filter(matches).length : 0;

  return (
    <>
      {schema.options.length > OPTION_FILTER_THRESHOLD && (
        <div className="option-filter-row">
          <input
            type="search"
            className="preset-filter"
            placeholder={`Filter ${schema.options.length} options by name or description...`}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          {q && (
            <span className="muted option-filter-count">
              {hitCount} match{hitCount === 1 ? "" : "es"}
            </span>
          )}
        </div>
      )}
      {schema.categories.map((cat) => {
        const opts = schema.options.filter((o) => o.category === cat && matches(o));
        if (opts.length === 0) return null;
        return (
          <details key={cat} className="settings-section yaml-builder-group" open>
            <summary>
              {cat} <span className="muted">({opts.length})</span>
            </summary>
            <div className="yaml-builder-group-body">
              {opts.map((opt) => (
                <div key={opt.name} className="yaml-builder-option">
                  <div className="yaml-builder-option-text">
                  <div className="yaml-builder-option-header">
                    <span className="yaml-builder-option-name">
                      {opt.display_name || opt.name}
                    </span>
                    <code className="yaml-builder-option-key">{opt.name}</code>
                  </div>
                  <OptionDescription text={opt.description} />
                  </div>
                  <div className="yaml-builder-option-control">
                    <OptionControl
                      option={opt}
                      value={values[opt.name]}
                      onChange={(v) => setValues((prev) => ({ ...prev, [opt.name]: v }))}
                    />
                  </div>
                </div>
              ))}
            </div>
          </details>
        );
      })}
    </>
  );
}

/**
 * An option's help text, as written by that apworld's author.
 *
 * Rendered as markdown because some authors write it that way: a sample of
 * 25 index worlds (2026-08-17) found 6% of descriptions using `**bold**`,
 * backticks or `-` bullets, which previously showed as literal syntax.
 * Plain-prose descriptions - the other 94% - render identically to before,
 * since remark-breaks keeps single newlines as line breaks.
 *
 * The text is third-party content from the index, so it goes through the
 * same MarkdownText component as room descriptions: no raw HTML, no
 * rehype-raw, external links forced to noopener.
 *
 * Long descriptions collapse to a few lines. AP docstrings routinely
 * enumerate every accepted value, which turns a 26-option form into a wall;
 * the toggle is per option and remembers nothing, so the default view stays
 * scannable without hiding anything.
 */
const DESC_CLAMP_CHARS = 180;

/** How many presets show before "Show N more", and when a filter box earns
 *  its place. Both exist for the fifty-presets-per-game case rather than
 *  today's handful. */
const PRESET_PREVIEW_COUNT = 4;
const PRESET_FILTER_THRESHOLD = 8;

/** Option count past which the options form earns a filter box. */
const OPTION_FILTER_THRESHOLD = 12;

function OptionDescription({ text }: { text?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;
  const long = text.length > DESC_CLAMP_CHARS;
  return (
    <div className="yaml-builder-option-desc">
      <div className={long && !expanded ? "yaml-builder-desc-clamp" : undefined}>
        <MarkdownText source={text} />
      </div>
      {long && (
        <button
          type="button"
          className="yaml-builder-desc-toggle"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

/**
 * The random modes a range accepts, in the order they are offered.
 * `random-range-<min>-<max>` takes its bounds from two extra inputs.
 */
const RANGE_RANDOM_MODES: { value: string; label: string }[] = [
  { value: "random", label: "Random" },
  { value: "random-low", label: "Random, low" },
  { value: "random-middle", label: "Random, middle" },
  { value: "random-high", label: "Random, high" },
  { value: "random-range", label: "Random in range…" },
];

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
    case "toggle": {
      // Three states rather than a checkbox: Archipelago accepts "random"
      // for a toggle and a checkbox cannot express it.
      const state = isRandomValue(value) ? "random" : value ? "on" : "off";
      return (
        <div className="yaml-builder-segmented" role="group">
          {(["off", "on", "random"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={state === s ? "is-active" : undefined}
              aria-pressed={state === s}
              onClick={() => onChange(s === "random" ? "random" : s === "on")}
            >
              {s}
            </button>
          ))}
        </div>
      );
    }

    case "choice":
      return (
        <select value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          {option.choices?.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
          {/* Archipelago picks uniformly among the game's own values. */}
          <option value="random">random</option>
        </select>
      );

    case "range": {
      const named = option.named_values;
      const isRandom = isRandomValue(value);
      const rangeMatch = isRandom
        ? /^random-range-(?:(low|middle|high)-)?(-?\d+)-(-?\d+)$/.exec(String(value))
        : null;
      const mode = !isRandom
        ? "fixed"
        : rangeMatch
        ? "random-range"
        : String(value);
      const num = typeof value === "number" ? value : Number(option.default);
      const matchingAlias = named
        ? Object.entries(named).find(([, v]) => v === num)?.[0]
        : undefined;
      const lo = rangeMatch ? Number(rangeMatch[2]) : (option.min ?? 0);
      const hi = rangeMatch ? Number(rangeMatch[3]) : (option.max ?? 0);
      return (
        <div className="range-input">
          <select
            className="yaml-builder-mode"
            value={mode}
            onChange={(e) => {
              const m = e.target.value;
              if (m === "fixed") onChange(option.default);
              else if (m === "random-range") {
                onChange(`random-range-${option.min ?? 0}-${option.max ?? 0}`);
              } else onChange(m);
            }}
          >
            <option value="fixed">Fixed value</option>
            {RANGE_RANDOM_MODES.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>

          {mode === "random-range" && (
            <div className="yaml-builder-range-bounds">
              <input
                type="number"
                min={option.min}
                max={option.max}
                value={lo}
                aria-label="Random range minimum"
                onChange={(e) => onChange(`random-range-${Number(e.target.value)}-${hi}`)}
              />
              <span>to</span>
              <input
                type="number"
                min={option.min}
                max={option.max}
                value={hi}
                aria-label="Random range maximum"
                onChange={(e) => onChange(`random-range-${lo}-${Number(e.target.value)}`)}
              />
            </div>
          )}

          {!isRandom && (
            <>
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
            </>
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
