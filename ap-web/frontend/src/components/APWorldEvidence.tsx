import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import type { APWorldVersion } from "../api";
import FuzzerModal from "./FuzzerModal";

function EvidenceButton({ label, tone, explanation, expanded, onClick }: {
  label: string; tone: string; explanation: string; expanded: boolean; onClick: () => void;
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
  const show = (element: HTMLButtonElement) => {
    const rect = element.getBoundingClientRect();
    const width = Math.min(288, window.innerWidth - 32);
    setPosition({ left: Math.max(16, Math.min(rect.left, window.innerWidth - width - 16)), ...(rect.top > 180 ? { bottom: window.innerHeight - rect.top + 8 } : { top: rect.bottom + 8 }) });
  };
  return <>
    <button type="button" className={`apworld-evidence-badge is-${tone}`} aria-describedby={position ? id : undefined} aria-expanded={expanded}
      onMouseEnter={event => show(event.currentTarget)} onMouseLeave={event => { if (!(event.relatedTarget instanceof Element) || event.relatedTarget.id !== id) setPosition(null); }}
      onFocus={event => show(event.currentTarget)} onBlur={() => setPosition(null)} onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); setPosition(null); } }}
      onClick={() => { setPosition(null); onClick(); }}><span aria-hidden="true" />{label}</button>
    {position && createPortal(<div id={id} role="tooltip" className={`apworld-evidence-tooltip is-${tone}`} style={position} onMouseLeave={() => setPosition(null)}><strong>{label}</strong><p>{explanation}</p><small>Activate the badge for details</small></div>, document.body)}
  </>;
}

export default function APWorldEvidence({ version }: { version?: APWorldVersion }) {
  const [detail, setDetail] = useState<"review" | "generation" | null>(null);
  const result = version?.fuzz_result;
  const testedAt = result ? new Date(result.fuzzed_at) : null;
  // Randomized failure rates cannot establish a canonical generation failure.
  const warnings = result && (result.verdict !== "clean" || result.default_rate > 0 || result.worst_hook_rate > 0);
  const reviewExplanation = "No release-specific security review is published in the catalog yet. This is not a safety clearance. Downloads and existing Builder availability are shown separately.";
  const generationExplanation = result
    ? warnings
      ? "Some recorded generation checks failed. Test your group's YAMLs before playing."
      : "The recorded randomized generation checks passed. This does not establish security, successful standard generation or a complete playthrough."
    : "No generation test result is recorded for this release yet.";
  return <>
    <div className="apworld-evidence-pair">
      <EvidenceButton label="Review pending" tone="pending" explanation={reviewExplanation} expanded={detail === "review"} onClick={() => setDetail(detail === "review" ? null : "review")} />
      <EvidenceButton label={result ? warnings ? "Generation warnings" : "Generation passed" : "Tests pending"} tone={result ? warnings ? "warning" : "passed" : "pending"} explanation={generationExplanation} expanded={detail === "generation"} onClick={() => setDetail(detail === "generation" ? null : "generation")} />
    </div>
    {testedAt && !Number.isNaN(testedAt.getTime()) && <p className="apworld-evidence-date">Tested {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(testedAt)}</p>}
    {detail === "review" && <div className="apworld-evidence-detail" role="region" aria-label="Security review explanation"><strong>Security review{version ? ` · v${version.version}` : ""}</strong><p>{reviewExplanation}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>}
    {detail === "generation" && (result ? <FuzzerModal result={result} version={version?.version} onClose={() => setDetail(null)} /> : <div className="apworld-evidence-detail" role="region" aria-label="Generation explanation"><p>{generationExplanation}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>)}
  </>;
}
