import { cloneElement, useEffect, useId, useState, type ReactElement } from "react";
import { createPortal } from "react-dom";

export default function Tooltip({ label, explanation, tone = "pending", hint, children }: {
  label: string; explanation: string; tone?: string; hint?: string; children: ReactElement;
}) {
  const id = useId();
  const [position, setPosition] = useState<{ left: number; top?: number; bottom?: number } | null>(null);
  useEffect(() => {
    if (!position) return;
    const hide = () => setPosition(null);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => { window.removeEventListener("scroll", hide, true); window.removeEventListener("resize", hide); };
  }, [position]);
  const show = (element: HTMLElement) => {
    const rect = element.getBoundingClientRect();
    const width = Math.min(288, window.innerWidth - 32);
    setPosition({ left: Math.max(16, Math.min(rect.left, window.innerWidth - width - 16)), ...(rect.top > 180 ? { bottom: window.innerHeight - rect.top + 8 } : { top: rect.bottom + 8 }) });
  };
  return <span className="apworld-tooltip-trigger"
    onMouseEnter={event => show(event.currentTarget)}
    onMouseLeave={event => { if (!(event.relatedTarget instanceof Node) || !document.getElementById(id)?.contains(event.relatedTarget)) setPosition(null); }}
    onFocus={event => { const element = event.currentTarget; requestAnimationFrame(() => { if (element.contains(document.activeElement)) show(element); }); }} onBlur={() => setPosition(null)}
    onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); setPosition(null); } }}
    onClickCapture={() => setPosition(null)}>
    {cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, { "aria-describedby": position ? id : undefined })}
    {position && createPortal(<div id={id} role="tooltip" className={`apworld-evidence-tooltip is-${tone}`} style={position} onMouseLeave={() => setPosition(null)}><strong>{label}</strong><p>{explanation}</p>{hint && <small>{hint}</small>}</div>, document.body)}
  </span>;
}
