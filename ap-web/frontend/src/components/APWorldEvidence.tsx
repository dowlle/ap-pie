import { useState } from "react";
import type { APWorldVersion } from "../api";
import FuzzerModal from "./FuzzerModal";

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
      <button type="button" className="apworld-evidence-badge is-pending" title={reviewExplanation} aria-expanded={detail === "review"} onClick={() => setDetail(detail === "review" ? null : "review")}><span aria-hidden="true" />Review pending</button>
      <button type="button" className={`apworld-evidence-badge is-${result ? warnings ? "warning" : "passed" : "pending"}`} title={generationExplanation} aria-expanded={detail === "generation"} onClick={() => setDetail(detail === "generation" ? null : "generation")}><span aria-hidden="true" />{result ? warnings ? "Generation warnings" : "Generation passed" : "Tests pending"}</button>
    </div>
    {testedAt && !Number.isNaN(testedAt.getTime()) && <p className="apworld-evidence-date">Tested {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(testedAt)}</p>}
    {warnings && <p className="apworld-evidence-note">{generationExplanation}</p>}
    {detail === "review" && <div className="apworld-evidence-detail" role="region" aria-label="Security review explanation"><strong>Security review{version ? ` · v${version.version}` : ""}</strong><p>{reviewExplanation}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>}
    {detail === "generation" && (result ? <FuzzerModal result={result} version={version?.version} onClose={() => setDetail(null)} /> : <div className="apworld-evidence-detail" role="region" aria-label="Generation explanation"><p>{generationExplanation}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>)}
  </>;
}
