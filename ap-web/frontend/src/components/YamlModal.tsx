import { useEffect, useMemo, useRef, useState } from "react";
import { diffLines } from "diff";
import {
  getPublicRoomYaml,
  updatePublicYaml,
  type PublicRoomYamlDetail,
  type UpdateYamlResult,
  type ValidationStatus,
} from "../api";
import { highlightYaml } from "../lib/yamlHighlight";

/**
 * Unified YAML modal: View / Edit / Diff in one dialog.
 *
 * Replaces the prior split YamlViewerModal + YamlEditModal - same content
 * surface, different actions per tab, no point making two modals.
 *
 *   - View: read-only, syntax-highlighted display of the current YAML.
 *           Always available. Opens here by default.
 *   - Edit: editable textarea with a syntax-highlighted overlay so what
 *           you type lights up the same way the View tab renders. Tab
 *           shown only when `canEdit`.
 *   - Diff: line-level red/green diff between current (View) and edited
 *           (Edit) content. Tab shown only when `canEdit` AND the user
 *           has actually changed something.
 *
 * Native <dialog> for focus-trap + Esc-close + ::backdrop styling.
 *
 * Backend contract for Edit: PUT /api/public/rooms/<id>/yamls/<yaml_id>
 * (FEAT-18). Same FEAT-13 auth gate the caller validates BEFORE setting
 * canEdit=true. Anonymous viewers and host-side viewers pass
 * canEdit=false; they only see the View tab.
 */

type TabKey = "view" | "edit" | "diff";

function badgeFor(status: ValidationStatus, error: string | null): { className: string; label: string; title?: string } {
  switch (status) {
    case "validated":
      return { className: "badge badge-done", label: "Validated" };
    case "manually_validated":
      return { className: "badge badge-trusted", label: "Host-trusted", title: "Marked valid by host" };
    case "unsupported":
      return { className: "badge badge-warn", label: "Unsupported", title: "apworld for this game isn't installed" };
    case "failed":
      return { className: "badge badge-error", label: "Failed", title: error ?? undefined };
    case "unknown":
    default:
      return { className: "badge badge-pending", label: "Pending" };
  }
}

// Both the textarea-with-overlay editor and the diff renderer normalise
// to "\n" line endings. The textarea returns \n on input regardless of
// OS, so loading a YAML with \r\n (uploaded from Windows) and diffing
// against the textarea content would otherwise flag every single line as
// changed even on a no-op edit. Strip them on load + everywhere we
// compare.
const normalizeLineEndings = (s: string): string => s.replace(/\r\n/g, "\n");

export default function YamlModal({
  roomId,
  yamlId,
  canEdit,
  initialTab,
  onClose,
  onUpdated,
  update,
}: {
  roomId: string;
  yamlId: number;
  /** When false, only the View tab is shown. When true, Edit + Diff are also
   *  available. Caller is responsible for the auth check before passing true. */
  canEdit: boolean;
  /** Default tab to open. Use "edit" when the caller wants the Edit pane
   *  immediately (e.g. clicked the Edit button on the row). Falls back to
   *  "view" for plain "view this YAML" entry points. */
  initialTab?: TabKey;
  onClose: () => void;
  onUpdated?: (result: UpdateYamlResult) => void;
  /** Override the submit endpoint. Defaults to updatePublicYaml (the
   *  submitter self-edit path). RoomDetail (host view) passes
   *  updateRoomYaml so the host edits hit the auth-gated host route
   *  instead, since the host isn't necessarily the submitter. */
  update?: (content: string) => Promise<UpdateYamlResult>;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<PublicRoomYamlDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editor, setEditor] = useState("");
  const [tab, setTab] = useState<TabKey>(initialTab ?? "view");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // View-tab toggle: AP YAML templates have huge ASCII-art comment
  // headers (Q&A about how to use the file, format docs, ...) that
  // bury the actual config below. This filters whole-line comments
  // (^\s*#) so the user can scan the live keys quickly. Inline
  // comments stay visible. Off by default.
  const [hideComments, setHideComments] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setLoadError(null);
    getPublicRoomYaml(roomId, yamlId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setEditor(normalizeLineEndings(d.yaml_content));
      })
      .catch((e) => {
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : "Failed to load YAML");
        }
      });
    return () => { cancelled = true; };
  }, [roomId, yamlId]);

  // The dialog opens once on mount and closes once on unmount. Re-running
  // showModal/close on every parent re-render would tear down the dialog's
  // focus + selection state - RoomPublic / RoomDetail poll every 5s and
  // pass a new inline onClose each time, which previously caused
  // text-selection in the Edit pane to drop after a few seconds
  // (pleb 2026-05-03).
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (!dlg.open) dlg.showModal();
    const onCancel = (e: Event) => { e.preventDefault(); onCloseRef.current(); };
    dlg.addEventListener("cancel", onCancel);
    return () => {
      dlg.removeEventListener("cancel", onCancel);
      if (dlg.open) dlg.close();
    };
  }, []);

  const onBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) onClose();
  };

  const original = normalizeLineEndings(detail?.yaml_content ?? "");
  const changed = canEdit && editor !== original;

  const diffParts = useMemo(() => {
    if (tab !== "diff") return null;
    if (!detail) return null;
    return diffLines(original, editor);
  }, [tab, detail, original, editor]);

  // If canEdit flips off mid-life (room closed under the modal), bounce
  // back to the View tab so the user isn't stuck on a tab they no longer
  // have access to.
  useEffect(() => {
    if (!canEdit && (tab === "edit" || tab === "diff")) {
      setTab("view");
    }
  }, [canEdit, tab]);

  const onPickFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = (reader.result as string) || "";
      setEditor(normalizeLineEndings(text));
      setSubmitError(null);
    };
    reader.onerror = () => setSubmitError("Could not read the file");
    reader.readAsText(f);
    e.target.value = "";
  };

  const submit = async () => {
    if (!changed || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Default to the public submitter-self-edit endpoint; the host
      // path (RoomDetail) overrides via the `update` prop. Both share
      // the same UpdateYamlResult shape.
      const updateFn = update ?? ((content: string) => updatePublicYaml(roomId, yamlId, content));
      const result = await updateFn(editor);
      onUpdated?.(result);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSubmitting(false);
    }
  };

  const badge = detail ? badgeFor(detail.validation_status, detail.validation_error) : null;
  const titlePrefix = tab === "edit" ? "Edit" : tab === "diff" ? "Diff" : "View";

  return (
    <dialog ref={dialogRef} onClick={onBackdropClick} className="yaml-modal">
      <header className="yaml-modal-header">
        <div className="yaml-modal-title">
          {detail ? (
            <>
              <strong>{titlePrefix}: {detail.player_name}</strong>
              <span className="muted yaml-modal-meta">
                {detail.game} · <span className="yaml-modal-filename">{detail.filename}</span>
              </span>
            </>
          ) : (
            <strong>{loadError ? "Failed to load" : "Loading…"}</strong>
          )}
        </div>
        {badge && <span className={badge.className} title={badge.title}>{badge.label}</span>}
        <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">✕</button>
      </header>

      {loadError && (
        <div className="yaml-modal-error">
          <strong>Couldn't load:</strong> {loadError}
        </div>
      )}

      {detail?.validation_error && tab === "view" && (
        <div className="yaml-modal-error">
          <strong>Validation error:</strong> {detail.validation_error}
        </div>
      )}

      {detail && (
        <>
          <nav className="yaml-modal-tabs" role="tablist">
            <TabBtn k="view" active={tab} onClick={setTab}>View</TabBtn>
            {canEdit && <TabBtn k="edit" active={tab} onClick={setTab}>Edit{changed ? " •" : ""}</TabBtn>}
            {canEdit && (
              <TabBtn
                k="diff"
                active={tab}
                onClick={setTab}
                disabled={!changed}
                title={!changed ? "Make a change to see the diff" : undefined}
              >
                Diff{changed ? " •" : ""}
              </TabBtn>
            )}
          </nav>

          <div className="yaml-modal-body">
            {tab === "view" && (
              <div className="yaml-modal-pane">
                <div className="yaml-modal-toolbar">
                  <label className="yaml-modal-checkbox">
                    <input
                      type="checkbox"
                      checked={hideComments}
                      onChange={(e) => setHideComments(e.target.checked)}
                    />
                    Hide comment lines
                  </label>
                  <span className="muted yaml-modal-hint">
                    Strips lines that start with <code>#</code>. Inline
                    comments stay visible.
                  </span>
                </div>
                <pre className="yaml-modal-view">
                  <code>
                    {highlightYaml(
                      hideComments
                        ? original
                            .split("\n")
                            .filter((l) => !/^\s*#/.test(l))
                            .join("\n")
                        : original,
                    )}
                  </code>
                </pre>
              </div>
            )}

            {tab === "edit" && canEdit && (
              <div className="yaml-modal-pane">
                <div className="yaml-modal-toolbar">
                  <label className="btn btn-sm yaml-modal-file-btn">
                    Replace from file…
                    <input
                      type="file"
                      accept=".yaml,.yml,text/yaml,text/plain"
                      onChange={onPickFile}
                      className="visually-hidden"
                    />
                  </label>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setEditor(original)}
                    disabled={!changed}
                  >
                    Reset to current
                  </button>
                  <span className="muted yaml-modal-hint">
                    Edit below or replace from file.
                  </span>
                </div>
                <HighlightedYamlEditor value={editor} onChange={setEditor} />
              </div>
            )}

            {tab === "diff" && diffParts && (
              <YamlDiffView parts={diffParts} />
            )}
          </div>
        </>
      )}

      {submitError && (
        <div className="yaml-modal-error">
          <strong>Save failed:</strong> {submitError}
        </div>
      )}

      <footer className="yaml-modal-footer">
        <span className="muted yaml-modal-status">
          {!detail ? "Loading…"
            : tab === "edit" || tab === "diff"
              ? changed
                ? countChangedLines(diffParts ?? diffLines(original, editor))
                : "No changes yet"
              : ""}
        </span>
        <div className="yaml-modal-actions">
          <button type="button" className="btn btn-sm" onClick={onClose}>Close</button>
          {canEdit && (
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={submit}
              disabled={!detail || !changed || submitting}
            >
              {submitting ? "Saving…" : "Save changes"}
            </button>
          )}
        </div>
      </footer>
    </dialog>
  );
}

function TabBtn({
  k,
  active,
  onClick,
  children,
  disabled,
  title,
}: {
  k: TabKey;
  active: TabKey;
  onClick: (k: TabKey) => void;
  children: React.ReactNode;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active === k}
      className={`yaml-modal-tab${active === k ? " is-active" : ""}`}
      onClick={() => onClick(k)}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  );
}

/**
 * Textarea with a syntax-highlighted overlay. Both layers share font /
 * size / line-height / padding / scroll position, so what the user types
 * lights up the same way the View tab renders.
 *
 * Standard "transparent textarea over highlighted pre" pattern. The
 * textarea owns input + caret; the pre is aria-hidden and renders the
 * highlighted token markup. We sync scrollTop/scrollLeft on every input
 * + scroll so they stay aligned at any cursor position.
 */
function HighlightedYamlEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (s: string) => void;
}) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const preRef = useRef<HTMLPreElement>(null);

  // Keep the highlighted pre's scroll glued to the textarea's. Run on
  // both `onScroll` and `onInput` so it tracks during typing too (the
  // browser scrolls the textarea when the caret moves below the visible
  // area; the pre needs to follow).
  const sync = () => {
    const ta = taRef.current;
    const pre = preRef.current;
    if (!ta || !pre) return;
    pre.scrollTop = ta.scrollTop;
    pre.scrollLeft = ta.scrollLeft;
  };

  useEffect(() => { sync(); }, [value]);

  return (
    <div className="yaml-edit-wrap">
      <pre ref={preRef} className="yaml-edit-highlight" aria-hidden="true">
        {/* Trailing newline matters: an empty trailing line would otherwise
            collapse and the caret would dangle a half-line below the
            highlighted text. */}
        {highlightYaml(value)}
        {value.endsWith("\n") ? "\n" : ""}
      </pre>
      <textarea
        ref={taRef}
        className="yaml-edit-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={sync}
        spellCheck={false}
        aria-label="YAML content"
      />
    </div>
  );
}

function YamlDiffView({
  parts,
}: {
  parts: { value: string; added?: boolean; removed?: boolean }[];
}) {
  const [showOnlyChanges, setShowOnlyChanges] = useState(false);
  const [contextLines, setContextLines] = useState(3);

  const rows = useMemo(() => {
    const out: { side: "+" | "-" | " "; text: string }[] = [];
    parts.forEach((p) => {
      const lines = p.value.split("\n");
      if (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
      const side: "+" | "-" | " " = p.added ? "+" : p.removed ? "-" : " ";
      for (const line of lines) out.push({ side, text: line });
    });
    return out;
  }, [parts]);

  const visibleRows = useMemo(() => {
    if (!showOnlyChanges) return rows.map((r) => ({ row: r, fold: 0 }));
    const out: { row: { side: "+" | "-" | " "; text: string }; fold: number }[] = [];
    let i = 0;
    while (i < rows.length) {
      if (rows[i].side === " ") {
        let j = i;
        while (j < rows.length && rows[j].side === " ") j++;
        const runLen = j - i;
        const head = i === 0 ? 0 : contextLines;
        const tail = j === rows.length ? 0 : contextLines;
        if (runLen <= head + tail) {
          for (let k = i; k < j; k++) out.push({ row: rows[k], fold: 0 });
        } else {
          for (let k = i; k < i + head; k++) out.push({ row: rows[k], fold: 0 });
          out.push({ row: { side: " ", text: "" }, fold: runLen - head - tail });
          for (let k = j - tail; k < j; k++) out.push({ row: rows[k], fold: 0 });
        }
        i = j;
      } else {
        out.push({ row: rows[i], fold: 0 });
        i++;
      }
    }
    return out;
  }, [rows, showOnlyChanges, contextLines]);

  return (
    <div className="yaml-diff-pane">
      <div className="yaml-modal-toolbar">
        <label className="yaml-modal-checkbox">
          <input
            type="checkbox"
            checked={showOnlyChanges}
            onChange={(e) => setShowOnlyChanges(e.target.checked)}
          />
          Only changes
        </label>
        {showOnlyChanges && (
          <label className="yaml-modal-checkbox">
            Context:
            <input
              type="number"
              min={0}
              max={20}
              value={contextLines}
              onChange={(e) => setContextLines(Math.max(0, Math.min(20, Number(e.target.value) || 0)))}
              style={{ width: "3.5rem", marginLeft: "0.3rem" }}
            />
          </label>
        )}
        <span className="muted yaml-modal-hint">
          <span className="yaml-diff-legend yaml-diff-add">+ added</span>
          <span className="yaml-diff-legend yaml-diff-remove">− removed</span>
        </span>
      </div>
      <div className="yaml-diff-rows" role="group" aria-label="YAML diff">
        {visibleRows.map((vr, idx) =>
          vr.fold > 0 ? (
            <div key={idx} className="yaml-diff-fold">
              … {vr.fold} unchanged line{vr.fold === 1 ? "" : "s"} …
            </div>
          ) : (
            <div
              key={idx}
              className={
                vr.row.side === "+"
                  ? "yaml-diff-row yaml-diff-add"
                  : vr.row.side === "-"
                  ? "yaml-diff-row yaml-diff-remove"
                  : "yaml-diff-row"
              }
            >
              <span className="yaml-diff-marker" aria-hidden="true">{vr.row.side}</span>
              <pre className="yaml-diff-text"><code>{highlightYaml(vr.row.text)}</code></pre>
            </div>
          ),
        )}
        {visibleRows.length === 0 && (
          <p className="muted">No changes detected.</p>
        )}
      </div>
    </div>
  );
}

function countChangedLines(
  parts: { value: string; added?: boolean; removed?: boolean }[],
): string {
  let added = 0;
  let removed = 0;
  for (const p of parts) {
    const n = p.value.split("\n").filter(
      (l, i, arr) => !(i === arr.length - 1 && l === ""),
    ).length;
    if (p.added) added += n;
    else if (p.removed) removed += n;
  }
  if (added === 0 && removed === 0) return "No line changes";
  return `${added} added, ${removed} removed`;
}
