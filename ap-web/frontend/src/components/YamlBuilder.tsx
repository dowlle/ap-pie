import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import type { BuilderSchemaEntry, Preset, TemplateOption } from "../api";
import { createPreset, getPresets, recordPresetUse, saveMyYaml } from "../api";
import { dump, load } from "js-yaml";
import { parseDocument } from "yaml";
import { buildYamlContent, downloadYaml, isRandomValue } from "../lib/yamlBuild";
import { CORE_CATEGORY, CORE_OPTIONS } from "../lib/coreOptions";
import { importYaml } from "../lib/yamlImport";
import { highlightYaml } from "../lib/yamlHighlight";
import MarkdownText from "./MarkdownText";
import { trackBuilderAbandoned, trackBuilderEmitted, trackBuilderOpened } from "../lib/analytics";
import type { ParseResponse } from "../workers/yamlParseWorker";

/**
 * FEAT-38: guided YAML builder modal. One shared shell for all three
 * mounts - RoomPublic (players), RoomDetail (hosts) and /apworlds (the
 * room-less "Create YAML" flow).
 *
 * Three steps: choose a preset (or defaults), change the auto-rendered
 * options, then review the emitted YAML (js-yaml, so quoting is always
 * valid) with Download
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
  presentation = "modal",
  draftKey,
  onGameChange,
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
  /** Full-page routes reuse the same builder state machine without native
   *  dialog focus, backdrop, or Escape behavior. */
  presentation?: "modal" | "page";
  /** sessionStorage key for route-level crash/refresh recovery. */
  draftKey?: string;
  onGameChange?: (apworldName: string) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const liveHighlightRef = useRef<HTMLPreElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  const [selected, setSelected] = useState<string>("");
  const [playerName, setPlayerName] = useState("Player1");
  const [values, setValues] = useState<Record<string, unknown>>({});
  // Archipelago-level options. Absent key = "leave the game default".
  const [coreValues, setCoreValues] = useState<Record<string, unknown>>({});
  const [step, setStep] = useState<"preset" | "options" | "review">("preset");
  // Non-null once the review step's YAML has been hand-edited.
  const [manualYaml, setManualYaml] = useState<string | null>(null);
  const [yamlSync, setYamlSync] = useState<"synced" | "typing" | "custom" | "error">("synced");
  const [yamlErrorKind, setYamlErrorKind] = useState<"syntax" | "schema" | "size" | null>(null);
  const [yamlWarningAccepted, setYamlWarningAccepted] = useState(false);
  const [yamlSyncMessage, setYamlSyncMessage] = useState("Form and YAML match.");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // FEAT-42: presets for the selected game. Published ones plus the
  // viewer's own drafts; the endpoint decides which.
  const [presets, setPresets] = useState<Preset[]>([]);
  const [presetsLoading, setPresetsLoading] = useState(false);
  const [savingPreset, setSavingPreset] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [presetFilter, setPresetFilter] = useState("");
  const [showAllPresets, setShowAllPresets] = useState(false);
  const [presetSaved, setPresetSaved] = useState("");
  const active = presentation === "page" || open;
  const yamlEditPendingRef = useRef(false);
  const applyingYamlRef = useRef(false);

  const entry = useMemo(
    () => games.find((g) => g.apworld_name === selected) ?? null,
    [games, selected],
  );

  const defaultValues = useMemo(() => {
    const defaults: Record<string, unknown> = {};
    for (const option of entry?.schema?.options ?? []) defaults[option.name] = option.default;
    return defaults;
  }, [entry]);

  const dirty = useMemo(
    () => !!entry && (
      playerName !== "Player1" ||
      Object.keys(coreValues).length > 0 ||
      JSON.stringify(values) !== JSON.stringify(defaultValues) ||
      manualYaml !== null
    ),
    [coreValues, defaultValues, entry, manualYaml, playerName, values],
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
    if (draftKey) sessionStorage.removeItem(draftKey);
    trackBuilderEmitted(entry.game, entry.version, action, roomId, manualYaml !== null);
  };

  const requestClose = () => {
    if (
      presentation === "page" && dirty && !emittedRef.current &&
      !window.confirm("Leave the YAML builder? Your draft will stay available in this tab.")
    ) return;
    onCloseRef.current();
  };
  const requestCloseRef = useRef(requestClose);
  useEffect(() => { requestCloseRef.current = requestClose; });

  // Native <dialog> lifecycle - same pattern as CreateRoomModal.
  useEffect(() => {
    if (presentation !== "modal") return;
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    else if (!open && dlg.open) dlg.close();
    const onCancel = (e: Event) => { e.preventDefault(); requestCloseRef.current(); };
    dlg.addEventListener("cancel", onCancel);
    return () => dlg.removeEventListener("cancel", onCancel);
  }, [open, presentation]);

  // Reset on open; preselect the requested (or only) game.
  useEffect(() => {
    if (!active) return;
    const first =
      (initialGame && games.some((g) => g.apworld_name === initialGame))
        ? initialGame
        : games.length === 1
        ? games[0].apworld_name
        : "";
    setSelected(first);
    setStep("preset");
    setBusy(false);
    setError("");
    setSuccess("");
    setManualYaml(null);
    setYamlSync("synced");
    setYamlErrorKind(null);
    setYamlWarningAccepted(false);
    setYamlSyncMessage("Form and YAML match.");
    setEditing(false);
    setCoreValues({});
    setPresets([]);
    setPresetFilter("");
    setShowAllPresets(false);
    setSavingPreset(false);
    setPresetName("");
    setPresetSaved("");
  }, [active, initialGame, games]);

  // FEAT-31: one "opened" per (open, game) pair - switching game inside an
  // open builder counts as opening the builder for that game, reopening the
  // same game after a close counts again.
  useEffect(() => {
    if (!active || !entry) return;
    const key = `${entry.apworld_name}@${entry.version}`;
    if (openedKeyRef.current === key) return;
    openedKeyRef.current = key;
    emittedRef.current = false;
    abandonReportedRef.current = false;
    trackBuilderOpened(entry.game, entry.version, surface, roomId);
  }, [active, entry, surface, roomId]);

  // Abandonment: fired when the builder closes (or the tab goes away) after
  // being opened for a game without producing a YAML.
  useEffect(() => {
    if (active) return;
    openedKeyRef.current = "";
  }, [active]);

  useEffect(() => {
    if (!active || !entry) return;
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
  }, [active, entry, roomId]);

  // Full-page builders recover unfinished work after a refresh. Session
  // storage keeps drafts local to this browser tab and avoids turning YAML
  // content into URL or server state.
  const restoredDraftKeyRef = useRef("");
  useEffect(() => {
    if (presentation !== "page" || !draftKey || !entry?.schema) return;
    if (restoredDraftKeyRef.current === draftKey) return;
    const raw = sessionStorage.getItem(draftKey);
    if (!raw) {
      restoredDraftKeyRef.current = draftKey;
      return;
    }
    try {
      const draft = JSON.parse(raw) as {
        playerName?: string;
        values?: Record<string, unknown>;
        coreValues?: Record<string, unknown>;
        manualYaml?: string | null;
        step?: "form" | "preset" | "options" | "review";
      };
      const timer = window.setTimeout(() => {
        if (draft.playerName) setPlayerName(draft.playerName);
        if (draft.values) setValues((current) => ({ ...current, ...draft.values }));
        if (draft.coreValues) setCoreValues(draft.coreValues);
        if (draft.manualYaml !== undefined) setManualYaml(draft.manualYaml);
        if (draft.step) setStep(draft.step === "form" ? "options" : draft.step);
        restoredDraftKeyRef.current = draftKey;
      }, 0);
      return () => window.clearTimeout(timer);
    } catch {
      sessionStorage.removeItem(draftKey);
      restoredDraftKeyRef.current = draftKey;
    }
  }, [draftKey, entry, presentation]);

  useEffect(() => {
    if (presentation !== "page" || !draftKey || !entry) return;
    if (restoredDraftKeyRef.current !== draftKey) return;
    if (!dirty || emittedRef.current) {
      sessionStorage.removeItem(draftKey);
      return;
    }
    sessionStorage.setItem(draftKey, JSON.stringify({
      playerName,
      values,
      coreValues,
      manualYaml,
      step,
    }));
  }, [coreValues, dirty, draftKey, entry, manualYaml, playerName, presentation, step, values]);

  useEffect(() => {
    if (presentation !== "page" || !dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      if (emittedRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, presentation]);

  // Seed form values from schema defaults whenever the game changes.
  // This must run before the saved-document effects below so imported
  // values layer over defaults instead of being overwritten by them.
  useEffect(() => {
    if (!entry?.schema) { setValues({}); return; }
    const defaults: Record<string, unknown> = {};
    for (const opt of entry.schema.options) defaults[opt.name] = opt.default;
    setValues(defaults);
    setStep("preset");
    setError("");
    setSuccess("");
  }, [entry]);

  // FEAT-43: import an existing document when one is handed in. Runs after
  // the defaults effect below has seeded the form, so imported values land
  // on top of defaults rather than under them.
  const importedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!active || !entry?.schema || !initialYaml) return;
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
    setStep("options");
  }, [active, entry, initialYaml]);

  // FEAT-43: a saved configuration, applied the same way a preset is.
  const importedValuesRef = useRef<Record<string, unknown> | null>(null);
  useEffect(() => {
    if (!active || !entry?.schema || !initialValues) return;
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
    setStep("options");
  }, [active, entry, initialValues, initialPlayerName]);

  // FEAT-42: load presets for whatever game is selected. Failure is silent:
  // presets are an aid, and a builder that still works without them is
  // better than an error banner over a form that is fine.
  useEffect(() => {
    if (!active || !entry) { setPresets([]); setPresetsLoading(false); return; }
    let cancelled = false;
    setPresetsLoading(true);
    getPresets(entry.apworld_name, entry.version)
      .then((list) => { if (!cancelled) setPresets(list); })
      .catch(() => { if (!cancelled) setPresets([]); })
      .finally(() => { if (!cancelled) setPresetsLoading(false); });
    return () => { cancelled = true; };
  }, [active, entry]);

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
      setStep("options");
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
    if (!entry?.schema) return "";
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
  }, [entry, playerName, values, coreValues]);

  // Hand-edited YAML wins over the generated document when present. The
  // builder only covers the options an apworld declares, so anything AP
  // supports centrally - progression_balancing, start_inventory, triggers,
  // multiple slots in one file - has to be reachable somehow, and until
  // those get real controls this is that path.
  const yamlContent = manualYaml ?? generatedYaml;

  const handleYamlEdit = (text: string) => {
    yamlEditPendingRef.current = true;
    setManualYaml(text);
    setYamlWarningAccepted(false);
    if (new TextEncoder().encode(text).byteLength > MAX_EDITABLE_YAML_BYTES) {
      yamlEditPendingRef.current = false;
      setYamlSync("error");
      setYamlErrorKind("size");
      setYamlSyncMessage("This YAML is larger than 64 KiB. Shorten it before saving, downloading or submitting.");
      return;
    }
    setYamlSync("typing");
    setYamlErrorKind(null);
    setYamlSyncMessage("Checking your YAML…");
  };

  const rebuildFromForm = () => {
    if (!entry?.schema) return;
    const normalized = { ...values };
    for (const option of entry.schema.options) {
      if (classifyYamlValue(option, normalized[option.name]) === "form") continue;
      if (option.type === "range" && typeof normalized[option.name] === "number") {
        const current = normalized[option.name] as number;
        normalized[option.name] = Math.min(
          option.max ?? current,
          Math.max(option.min ?? current, current),
        );
      } else {
        normalized[option.name] = option.default;
      }
    }
    const normalizedCore = { ...coreValues };
    for (const option of CORE_OPTIONS) {
      if (normalizedCore[option.name] === undefined) continue;
      if (classifyYamlValue(option, normalizedCore[option.name]) !== "form") {
        delete normalizedCore[option.name];
      }
    }
    setValues(normalized);
    setCoreValues(normalizedCore);
    setManualYaml(null);
    setEditing(false);
    setYamlSync("synced");
    setYamlErrorKind(null);
    setYamlWarningAccepted(false);
    setYamlSyncMessage("Rebuilt from valid form values.");
  };

  // YAML → form. Wait until the visitor pauses so partially typed YAML is
  // never replaced. Valid values flow back to their controls; values the
  // generic form cannot represent remain in the document and are labelled
  // custom rather than silently coerced.
  useEffect(() => {
    const syncSchema = entry?.schema;
    if (manualYaml === null || !syncSchema) return;
    if (new TextEncoder().encode(manualYaml).byteLength > MAX_EDITABLE_YAML_BYTES) return;
    let worker: Worker | null = null;
    const timer = window.setTimeout(() => {
      worker = new Worker(new URL("../workers/yamlParseWorker.ts", import.meta.url), { type: "module" });
      worker.onmessage = (event: MessageEvent<ParseResponse>) => {
        worker?.terminate();
        worker = null;
        if (!event.data.ok) {
          yamlEditPendingRef.current = false;
          setYamlSync("error");
          setYamlErrorKind("syntax");
          setYamlSyncMessage(event.data.message);
          return;
        }
        const parsed = event.data.parsed;
        const custom: string[] = [...parsed.unknown, ...parsed.extraRootKeys];
        const invalid: string[] = [];
        for (const option of syncSchema.options) {
          const issue = classifyYamlValue(option, parsed.values[option.name]);
          if (issue === "custom") custom.push(option.name);
          if (issue === "invalid") invalid.push(option.name);
        }

        applyingYamlRef.current = true;
        if (parsed.playerName) setPlayerName(parsed.playerName);
        setValues({ ...defaultValues, ...parsed.values });
        setCoreValues(parsed.coreValues);
        yamlEditPendingRef.current = false;
        if (invalid.length > 0) {
          setYamlSync("error");
          setYamlErrorKind("schema");
          setYamlSyncMessage(`${invalid.length} value${invalid.length === 1 ? " is" : "s are"} outside what this APWorld version accepts: ${invalid.slice(0, 3).join(", ")}.`);
        } else if (custom.length > 0) {
          setYamlSync("custom");
          setYamlErrorKind(null);
          setYamlSyncMessage(`${custom.length} custom field${custom.length === 1 ? " is" : "s are"} preserved in YAML even though the form cannot fully represent ${custom.length === 1 ? "it" : "them"}.`);
        } else {
          setYamlSync("synced");
          setYamlErrorKind(null);
          setYamlSyncMessage("Form and YAML match.");
        }
      };
      worker.onerror = () => {
        worker?.terminate();
        worker = null;
        yamlEditPendingRef.current = false;
        setYamlSync("error");
        setYamlErrorKind("syntax");
        setYamlSyncMessage("The YAML checker could not finish. Try editing the document again.");
      };
      worker.postMessage({ text: manualYaml, schema: syncSchema });
    }, 350);
    return () => {
      window.clearTimeout(timer);
      worker?.terminate();
    };
  }, [defaultValues, entry, manualYaml]);

  // Form → YAML. The Document API changes known nodes in-place and keeps
  // unsupported sections, comments and ordering. If the visitor is midway
  // through invalid YAML, form changes pause instead of overwriting it.
  const lastGeneratedRef = useRef("");
  useEffect(() => {
    if (!generatedYaml) return;
    if (!lastGeneratedRef.current) {
      lastGeneratedRef.current = generatedYaml;
      return;
    }
    if (generatedYaml === lastGeneratedRef.current) return;
    lastGeneratedRef.current = generatedYaml;
    if (applyingYamlRef.current) {
      applyingYamlRef.current = false;
      return;
    }
    if (manualYaml === null || !entry?.schema || yamlEditPendingRef.current) return;
    const document = parseDocument(manualYaml);
    if (document.errors.length > 0) return;
    document.setIn(["name"], playerName.trim() || "Player1");
    for (const option of entry.schema.options) {
      document.setIn([entry.game, option.name], values[option.name]);
    }
    for (const option of CORE_OPTIONS) {
      if (coreValues[option.name] === undefined || coreValues[option.name] === "") {
        document.deleteIn([entry.game, option.name]);
      } else {
        document.setIn([entry.game, option.name], coreValues[option.name]);
      }
    }
    setManualYaml(document.toString({ lineWidth: 0 }));
    setYamlSync("synced");
    setYamlErrorKind(null);
    setYamlSyncMessage("Form change applied without removing your custom YAML.");
  }, [coreValues, entry, generatedYaml, manualYaml, playerName, values]);

  /** Player name + game as they appear in the document being submitted.
   *  A hand-edit may have changed `name:`, and the room endpoints take the
   *  player name as its own field, so read it back rather than trusting
   *  the form. */
  const submittedIdentity = useMemo(() => ({
      playerName: playerName.trim() || "Player1",
      game: entry?.game ?? "",
  }), [playerName, entry]);

  const handleSubmit = async () => {
    if (!submit || !yamlContent || !entry || !canFinalize) return;
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
    if (e.target === dialogRef.current) requestClose();
  };

  const schema = entry?.schema ?? null;
  const canFinalize = yamlSync !== "typing" && (
    yamlSync !== "error" || (yamlErrorKind === "schema" && yamlWarningAccepted)
  );

  const builderContent = (
    <>
      <header className="settings-modal-header">
        <div className="settings-modal-title">
          <strong>Build your YAML</strong>
          {entry && (
            <span className="settings-modal-meta">
              {entry.display_name} · v{entry.version}
            </span>
          )}
        </div>
        <button type="button" className="btn btn-sm" onClick={requestClose} aria-label={presentation === "page" ? "Back" : "Close"}>
          {presentation === "page" ? "← Back" : "✕"}
        </button>
      </header>

      {presentation === "page" && (
        <nav className="yaml-builder-steps" aria-label="YAML builder steps">
          <button
            type="button"
            className={step === "preset" ? "is-active" : undefined}
            aria-current={step === "preset" ? "step" : undefined}
            onClick={() => { setError(""); setSuccess(""); setEditing(false); setStep("preset"); }}
          >
            <span>1</span> Pick a preset
          </button>
          <span className="yaml-builder-step-line" aria-hidden="true">→</span>
          <button
            type="button"
            className={step === "options" ? "is-active" : undefined}
            aria-current={step === "options" ? "step" : undefined}
            disabled={!schema}
            onClick={() => { setError(""); setSuccess(""); setEditing(false); setStep("options"); }}
          >
            <span>2</span> Change your options
          </button>
          <span className="yaml-builder-step-line" aria-hidden="true">→</span>
          <button
            type="button"
            className={step === "review" ? "is-active" : undefined}
            aria-current={step === "review" ? "step" : undefined}
            disabled={!schema || !playerName.trim()}
            onClick={() => { setError(""); setStep("review"); }}
          >
            <span>3</span> Review and finish
          </button>
        </nav>
      )}

      <div className="settings-modal-body">
        {step === "preset" && (
          <section className="settings-section yaml-builder-preset-step">
            <h3>Pick a starting point</h3>
            <p className="settings-hint">
              A preset fills in a ready-made setup. You can change every option in the next step.
            </p>
            <button
              type="button"
              className="btn btn-primary yaml-builder-default-start"
              disabled={!schema}
              onClick={() => { setError(""); setManualYaml(null); setStep("options"); }}
            >
              Start with the game defaults
            </button>
            {presetsLoading && <p className="settings-hint">Loading presets…</p>}
            {!presetsLoading && presets.length > 0 && (
              <div className="yaml-builder-preset-list-wrap">
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
                          {p.kind === "advanced" && <span className="badge badge-save">advanced</span>}
                          {p.status === "private" && <span className="badge">draft</span>}
                        </div>
                        {p.description && <p className="preset-row-desc">{p.description}</p>}
                        <p className="preset-row-meta">
                          {p.author_username ? `by ${p.author_username}` : "by an unknown author"}
                          {` · ${p.uses === 1 ? "used once" : `used ${p.uses} times`}`}
                          {p.score > 0 && ` · ${p.score} upvote${p.score === 1 ? "" : "s"}`}
                          {p.version !== entry?.version && ` · written for v${p.version}`}
                          {p.stale_keys.length > 0 && ` · ${p.stale_keys.length} old option${p.stale_keys.length === 1 ? "" : "s"} skipped`}
                        </p>
                      </div>
                      <button type="button" className="btn btn-sm preset-use-btn" onClick={() => applyPreset(p)}>
                        Use this
                      </button>
                    </li>
                  ))}
                </ul>
                {filteredPresets.length === 0 && <p className="settings-hint">No presets match that filter.</p>}
                {hiddenPresetCount > 0 && (
                  <button type="button" className="yaml-builder-desc-toggle" onClick={() => setShowAllPresets(true)}>
                    Show {hiddenPresetCount} more preset{hiddenPresetCount === 1 ? "" : "s"}
                  </button>
                )}
                {showAllPresets && filteredPresets.length > PRESET_PREVIEW_COUNT && (
                  <button type="button" className="yaml-builder-desc-toggle" onClick={() => setShowAllPresets(false)}>
                    Show fewer
                  </button>
                )}
              </div>
            )}
            {!presetsLoading && presets.length === 0 && (
              <p className="settings-aux-note">There are no shared presets for this game yet. The game defaults are a safe place to begin.</p>
            )}
          </section>
        )}

        {step === "options" && (
          <fieldset className="yaml-builder-form-fieldset" disabled={yamlSync === "typing"}>
            {yamlSync === "typing" && (
              <p className="yaml-builder-form-lock" role="status">
                Checking the YAML edit before the form changes again…
              </p>
            )}
            <section className="settings-section">
              <h3>Player</h3>
              <div className="settings-controls yaml-builder-toprow">
                {games.length > 1 && (
                  <label className="yaml-builder-field">
                    <span>Game</span>
                    <select
                      value={selected}
                      onChange={(e) => {
                        setSelected(e.target.value);
                        if (e.target.value) onGameChange?.(e.target.value);
                      }}
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
          </fieldset>
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
                    disabled={busy || !canFinalize}
                    onClick={handleSaveToLibrary}
                    title="Keep this YAML in your own library so you can reopen or reuse it"
                  >
                    Save to my YAMLs
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={!canFinalize}
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
                    disabled={busy || !presetName.trim() || !canFinalize}
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
                  onChange={(e) => handleYamlEdit(e.target.value)}
                  rows={18}
                  aria-label="YAML content"
                />
              ) : presentation === "modal" ? (
                <pre className="yaml-builder-preview">{highlightYaml(yamlContent)}</pre>
              ) : (
                <>
                  <p className="settings-aux-note yaml-builder-page-review-note">
                    The live document stays visible on the right while you save, download, or submit it.
                  </p>
                  <pre className="yaml-builder-preview yaml-builder-page-mobile-preview">
                    {highlightYaml(yamlContent)}
                  </pre>
                </>
              )}
              {manualYaml !== null && (
                <p className="settings-aux-note yaml-builder-manual-note" role="status" aria-live="polite">
                  {yamlSyncMessage}{" "}
                  <button
                    type="button"
                    className="yaml-builder-desc-toggle"
                    onClick={rebuildFromForm}
                  >
                    Discard edits and rebuild from the form
                  </button>
                </p>
              )}
              {yamlErrorKind === "schema" && !yamlWarningAccepted && (
                <div className="yaml-builder-warning-gate" role="alert">
                  <strong>Review the invalid value before finishing.</strong>
                  <span>You can correct it in the form or explicitly keep the hand-written YAML.</span>
                  <button type="button" className="btn btn-sm" onClick={() => setYamlWarningAccepted(true)}>
                    Continue with this warning
                  </button>
                </div>
              )}
              {(yamlErrorKind === "syntax" || yamlErrorKind === "size") && (
                <p className="settings-error" role="alert">
                  Fix the YAML before downloading, saving or submitting it.
                </p>
              )}
            </section>
            {reviewExtra && !success && canFinalize && reviewExtra(yamlContent, submittedIdentity.playerName)}
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
        {step === "preset" && (
          <>
            <button type="button" className="btn btn-sm" onClick={requestClose}>Cancel</button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={!schema}
              onClick={() => setStep("options")}
            >
              Continue with defaults →
            </button>
          </>
        )}
        {step === "options" && (
          <>
            <button type="button" className="btn btn-sm" onClick={() => setStep("preset")}>← Back to presets</button>
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
              onClick={() => { setError(""); setSuccess(""); setEditing(false); setStep("options"); }}
              disabled={busy}
              title={
                manualYaml !== null
                  ? "Your hand-edits are kept; changing the form again will not overwrite them until you discard them"
                  : undefined
              }
            >
              ← Back to options
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
              disabled={busy || !canFinalize}
            >
              Download .yaml
            </button>
            {submit && !success && (
              <button
                type="button"
                className="btn btn-sm btn-primary"
                onClick={handleSubmit}
                disabled={busy || !canFinalize}
              >
                {busy ? "Submitting…" : submit.label}
              </button>
            )}
            {success && (
              <button type="button" className="btn btn-sm btn-primary" onClick={requestClose}>
                Done
              </button>
            )}
          </>
        )}
      </footer>
    </>
  );

  if (presentation === "page") {
    return (
      <div className="yaml-builder-page">
        <div className="yaml-builder-workspace-form">{builderContent}</div>
        <aside className="yaml-builder-live" aria-label="Live YAML preview">
          <div className="yaml-builder-live-head">
            <div>
              <strong>Live YAML</strong>
              <span>Edit here or change the form</span>
            </div>
            <div className="yaml-builder-live-statuses">
              <span className={`yaml-builder-sync-status is-${yamlSync}`} role="status" aria-live="polite">{yamlSync === "error" ? "Needs attention" : yamlSync === "custom" ? "Custom values" : yamlSync === "typing" ? "Typing…" : "Synced"}</span>
              {entry && <span className="badge">v{entry.version}</span>}
            </div>
          </div>
          <div
            className="yaml-builder-live-editor-shell"
            style={{ "--yaml-lines": Math.max(1, yamlContent.split("\n").length) } as CSSProperties}
          >
            <pre ref={liveHighlightRef} className="yaml-builder-live-highlight" aria-hidden="true">
              {yamlContent ? highlightYaml(yamlContent) : "Choose a game to start building."}
            </pre>
            <textarea
              className="yaml-builder-live-editor"
              value={yamlContent}
              onChange={(event) => handleYamlEdit(event.target.value)}
              onScroll={(event) => {
                if (!liveHighlightRef.current) return;
                liveHighlightRef.current.scrollTop = event.currentTarget.scrollTop;
                liveHighlightRef.current.scrollLeft = event.currentTarget.scrollLeft;
              }}
              spellCheck={false}
              aria-label="Editable live YAML"
            />
          </div>
          <p className={`settings-aux-note yaml-builder-live-note is-${yamlSync}`}>
            {yamlSyncMessage}
            {manualYaml !== null && (
              <>{" "}<button type="button" className="yaml-builder-desc-toggle" onClick={rebuildFromForm}>Rebuild from form</button></>
            )}
          </p>
        </aside>
      </div>
    );
  }

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="settings-modal yaml-builder-modal">
      {builderContent}
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
 * Long descriptions collapse only when doing so actually shortens the row.
 * The browser measures the full and clamped text columns against the option
 * control, so a tall control can use the otherwise-empty space beside it.
 */
/** How many presets show before "Show N more", and when a filter box earns
 *  its place. Both exist for the fifty-presets-per-game case rather than
 *  today's handful. */
const PRESET_PREVIEW_COUNT = 4;
const PRESET_FILTER_THRESHOLD = 8;

/** Option count past which the options form earns a filter box. */
const OPTION_FILTER_THRESHOLD = 12;
const MAX_EDITABLE_YAML_BYTES = 64 * 1024;

function classifyYamlValue(option: TemplateOption, value: unknown): "form" | "custom" | "invalid" {
  if (value === undefined) return "form";
  if (typeof value === "object" && value !== null && option.type !== "list" && option.type !== "dict") {
    return "custom"; // Weighted YAML values are valid AP input, but not one form value.
  }
  if (isRandomValue(value)) return "form";
  switch (option.type) {
    case "toggle":
      return typeof value === "boolean" ? "form" : "invalid";
    case "choice":
      return typeof value === "string" && option.choices?.includes(value) ? "form" : "invalid";
    case "range":
      return typeof value === "number" && value >= (option.min ?? value) && value <= (option.max ?? value)
        ? "form"
        : "invalid";
    case "list":
      return Array.isArray(value) ? "form" : "invalid";
    case "dict":
      return typeof value === "object" && value !== null && !Array.isArray(value) ? "form" : "invalid";
    default:
      return typeof value === "string" || typeof value === "number" ? "form" : "custom";
  }
}

function OptionDescription({ text }: { text?: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const [canCollapse, setCanCollapse] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const root = rootRef.current;
    const row = root?.closest<HTMLElement>(".yaml-builder-option");
    const textColumn = root?.closest<HTMLElement>(".yaml-builder-option-text");
    const control = row?.querySelector<HTMLElement>(".yaml-builder-option-control");
    if (!root || !row || !textColumn || !control) return;

    const measure = () => {
      const width = textColumn.getBoundingClientRect().width;
      if (width <= 0) return;
      const cloneHeight = (clamped: boolean) => {
        const clone = textColumn.cloneNode(true) as HTMLElement;
        clone.querySelectorAll("button").forEach((button) => button.remove());
        const content = clone.querySelector<HTMLElement>(".yaml-builder-option-desc-content");
        content?.classList.toggle("yaml-builder-desc-clamp", clamped);
        Object.assign(clone.style, {
          position: "fixed",
          visibility: "hidden",
          pointerEvents: "none",
          inset: "0 auto auto -10000px",
          width: `${width}px`,
        });
        document.body.appendChild(clone);
        const height = clone.getBoundingClientRect().height;
        clone.remove();
        return height;
      };

      const clampedHeight = cloneHeight(true);
      const fullHeight = cloneHeight(false);
      const textRect = textColumn.getBoundingClientRect();
      const controlRect = control.getBoundingClientRect();
      const stacked = controlRect.top >= textRect.bottom - 1;
      const actuallyOverflows = fullHeight > clampedHeight + 1;
      setCanCollapse(
        actuallyOverflows && (stacked || fullHeight > controlRect.height + 1),
      );
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(row);
    observer.observe(control);
    return () => observer.disconnect();
  }, [text]);

  if (!text) return null;
  return (
    <div className="yaml-builder-option-desc" ref={rootRef}>
      <div className={`yaml-builder-option-desc-content${canCollapse && !expanded ? " yaml-builder-desc-clamp" : ""}`}>
        <MarkdownText source={text} />
      </div>
      {canCollapse && (
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
      const state = isRandomValue(value) ? "random" : typeof value === "boolean" ? (value ? "on" : "off") : "custom";
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
          {state === "custom" && <span className="yaml-builder-custom-value">Custom: {String(value)}</span>}
        </div>
      );
    }

    case "choice":
      {
      const choiceValue = String(value ?? "");
      const known = option.choices?.includes(choiceValue) || choiceValue === "random";
      return (
        <select value={choiceValue} onChange={(e) => onChange(e.target.value)}>
          {!known && <option value={choiceValue}>Custom YAML value: {choiceValue}</option>}
          {option.choices?.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
          {/* Archipelago picks uniformly among the game's own values. */}
          <option value="random">random</option>
        </select>
      );
      }

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
      const outside = !isRandom && typeof value === "number" && (
        value < (option.min ?? value) || value > (option.max ?? value)
      );
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
              {outside && (
                <div className="yaml-builder-value-warning">
                  <span>{String(value)} is outside {option.min}–{option.max}.</span>
                  <button
                    type="button"
                    className="yaml-builder-desc-toggle"
                    onClick={() => onChange(Math.min(option.max ?? value, Math.max(option.min ?? value, value)))}
                  >
                    Use nearest valid value
                  </button>
                </div>
              )}
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
