import { type ReactNode } from "react";

/**
 * Styled file-input drop zone, replacing raw <input type="file"> on
 * public-facing pages.
 *
 * The browser default `<input type="file">` renders as an OS button with
 * "No file chosen" text - fine for an admin form, jarring on a polished
 * public page. This wraps a (visually hidden, full-area-overlay) input in
 * a real call-to-action <label>: dashed border, file icon, headline + hint
 * text, optional progress indicator while a submission is in flight.
 *
 * Implemented as a <label> so the browser triggers the wrapped <input>
 * natively on click - no programmatic `.click()` trampoline. That's
 * deliberate: BUG-02 was Chrome double-firing the picker when the picker
 * was opened from a JS click handler that was itself reacting to a click
 * on a parent element (the click bubbled to the parent AND the parent
 * called .click() → two opens). Native <label> semantics fire it once.
 *
 * The page-level useFileDropZone overlay handles the drag case at page root.
 */
export default function DropZone({
  onFiles,
  accept = ".yaml,.yml",
  multiple = true,
  busy = false,
  busyLabel,
  headline = "Drop YAML files here",
  hint = "or click to browse",
  icon = "⤓",
  children,
}: {
  onFiles: (files: File[]) => void | Promise<void>;
  accept?: string;
  multiple?: boolean;
  busy?: boolean;
  busyLabel?: string;
  headline?: string;
  hint?: string;
  icon?: ReactNode;
  children?: ReactNode;
}) {
  const onChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    await onFiles(files);
    // Reset so re-selecting the same file fires onChange again.
    e.target.value = "";
  };

  return (
    <label
      className={`dropzone${busy ? " dropzone--busy" : ""}`}
      aria-busy={busy || undefined}
    >
      <span className="dropzone-icon" aria-hidden="true">{icon}</span>
      <span className="dropzone-headline">{headline}</span>
      <span className="dropzone-hint">{hint}</span>
      {busy && busyLabel && (
        <span className="dropzone-progress">
          <span className="dropzone-spinner" aria-hidden="true" />
          {busyLabel}
        </span>
      )}
      {children}
      <input
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={onChange}
        disabled={busy}
        className="dropzone-input"
        aria-label={headline}
      />
    </label>
  );
}
