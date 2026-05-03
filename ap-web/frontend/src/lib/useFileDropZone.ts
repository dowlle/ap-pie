import { useCallback, useRef, useState } from "react";

/**
 * Page-level file drag-and-drop hook.
 *
 * Returns drag event handlers you spread onto a wrapping div, plus an
 * `isDragging` flag for rendering a visual cue. The handlers use the
 * dragenter/dragleave counter pattern to avoid the flicker that naive
 * implementations get when the cursor crosses child element boundaries
 * (each crossing fires both events). Only file drags trigger the state -
 * dragging text or images won't activate the drop zone.
 *
 * The drop event fires on the wrapping element regardless of which child
 * the user actually drops on, because `dragover` / `drop` bubble up through
 * the React event system. This makes it safe to wrap an entire page.
 */
export function useFileDropZone(opts: {
  onFiles: (files: File[]) => void | Promise<void>;
  enabled?: boolean;
}) {
  const enabled = opts.enabled ?? true;
  const [isDragging, setIsDragging] = useState(false);
  const counterRef = useRef(0);

  const isFileDrag = (dataTransfer: DataTransfer | null) => {
    if (!dataTransfer) return false;
    const types = Array.from(dataTransfer.types ?? []);
    return types.includes("Files");
  };

  const reset = useCallback(() => {
    counterRef.current = 0;
    setIsDragging(false);
  }, []);

  const onDragEnter = useCallback((e: React.DragEvent) => {
    if (!enabled) return;
    if (!isFileDrag(e.dataTransfer)) return;
    e.preventDefault();
    counterRef.current += 1;
    if (counterRef.current === 1) setIsDragging(true);
  }, [enabled]);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!enabled) return;
    if (!isFileDrag(e.dataTransfer)) return;
    e.preventDefault();
    counterRef.current = Math.max(0, counterRef.current - 1);
    if (counterRef.current === 0) setIsDragging(false);
  }, [enabled]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    if (!enabled) return;
    if (!isFileDrag(e.dataTransfer)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, [enabled]);

  const onDrop = useCallback(async (e: React.DragEvent) => {
    if (!enabled) return;
    e.preventDefault();
    reset();
    const files = Array.from(e.dataTransfer.files ?? []);
    if (files.length === 0) return;
    await opts.onFiles(files);
  }, [enabled, opts, reset]);

  return {
    isDragging,
    handlers: { onDragEnter, onDragLeave, onDragOver, onDrop },
  };
}
