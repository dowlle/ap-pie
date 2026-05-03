/**
 * Full-page visual feedback for an active file drag.
 *
 * Rendered conditionally when a `useFileDropZone` reports `isDragging`.
 * `pointer-events: none` means the actual drop event still fires on the
 * dropzone-wrapped element underneath - this is purely a visual layer.
 */
export default function DropOverlay({ label }: { label: string }) {
  return (
    <div
      className="drop-overlay"
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        pointerEvents: "none",
        background: "rgba(232, 168, 87, 0.10)",
        border: "4px dashed var(--accent, #e8a857)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          background: "var(--bg-elevated, #1c1c1c)",
          color: "var(--text, #eee)",
          padding: "1rem 2rem",
          borderRadius: "10px",
          fontWeight: 500,
          fontSize: "1.05rem",
          boxShadow: "0 8px 32px rgba(0,0,0,0.45), 0 0 0 1px var(--border-strong, #3a3340)",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.6rem",
        }}
      >
        <span aria-hidden="true" style={{ fontSize: "1.25em" }}>⤓</span>
        {label}
      </div>
    </div>
  );
}
