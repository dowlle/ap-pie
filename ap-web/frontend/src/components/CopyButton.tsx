import { useState } from "react";
import { copyText } from "../lib/copy";

/**
 * Single source of truth for "copy this string to clipboard" buttons.
 * Was previously duplicated across Play, RoomPublic, RoomDetail and ShareGame
 * with three different label conventions and two different behaviours when
 * copyText returned false.
 */
export default function CopyButton({
  value,
  label = "Copy",
  copiedLabel = "Copied!",
  className = "btn btn-sm",
  variant,
}: {
  value: string;
  label?: string;
  copiedLabel?: string;
  className?: string;
  variant?: "primary" | "default";
}) {
  const [copied, setCopied] = useState(false);
  const onClick = async () => {
    const ok = await copyText(value);
    if (!ok) return;
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  const cls = variant === "primary" ? `${className} btn-primary` : className;
  return (
    <button type="button" className={cls} onClick={onClick}>
      {copied ? copiedLabel : label}
    </button>
  );
}
