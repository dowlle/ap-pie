import { useState } from "react";
import Tooltip from "./Tooltip";
import type { APWorldVersion } from "../api";
import FuzzerModal from "./FuzzerModal";

function EvidenceButton({ label, tone, explanation, expanded, onClick }: {
  label: string; tone: string; explanation: string; expanded: boolean; onClick: () => void;
}) {
  return <Tooltip label={label} tone={tone} explanation={explanation} hint="Activate the badge for details">
    <button type="button" className={`apworld-evidence-badge is-${tone}`} aria-expanded={expanded} onClick={onClick}><span aria-hidden="true" />{label}</button>
  </Tooltip>;
}

export default function APWorldEvidence({ version, builtin = false, reviewOpen, onReviewChange }: {
  version?: APWorldVersion; builtin?: boolean; reviewOpen?: boolean; onReviewChange?: (open: boolean) => void;
}) {
  const [detail, setDetail] = useState<"review" | "generation" | null>(null);
  const reviewVisible = reviewOpen ?? detail === "review";
  const changeReview = (open: boolean) => { onReviewChange?.(open); setDetail(open ? "review" : null); };
  const result = version?.fuzz_result;
  const testedAt = result ? new Date(result.fuzzed_at) : null;
  // Randomized failure rates cannot establish a canonical generation failure.
  const warnings = result && (result.verdict !== "clean" || result.default_rate > 0 || result.worst_hook_rate > 0);
  const review = version?.security_review;
  const builtinRelease = builtin && (!version || version.source === "builtin");
  const reviewLabels = { pass: "Review passed", needs_review: "Review concerns", fail: "Review failed", held: "Review held", human_accepted: "Concerns accepted" };
  const reviewLabel = review ? reviewLabels[review.status] : builtinRelease ? "Review not applicable" : "Review pending";
  const reviewTone = review ? review.status === "pass" ? "passed" : review.status === "fail" ? "failed" : "warning" : "pending";
  const reviewExplanation = review?.summary ?? (builtinRelease
    ? "This world ships with Archipelago. There is no separate downloadable APWorld release to review here. Built-in provenance is not a security guarantee."
    : "No matching security review is recorded for these exact release bytes. This is not a safety clearance. Downloads and existing Builder availability are shown separately.");
  const generationExplanation = result
    ? warnings
      ? "Some recorded generation checks failed. Test your group's YAMLs before playing."
      : "The recorded randomized generation checks passed. This does not establish security, successful standard generation or a complete playthrough."
    : "No generation test result is recorded for this release yet.";
  return <>
    <div className="apworld-evidence-pair">
      <EvidenceButton label={reviewLabel} tone={reviewTone} explanation={reviewExplanation} expanded={reviewVisible} onClick={() => changeReview(!reviewVisible)} />
      <EvidenceButton label={result ? warnings ? "Generation warnings" : "Generation passed" : "Tests pending"} tone={result ? warnings ? "warning" : "passed" : "pending"} explanation={generationExplanation} expanded={detail === "generation"} onClick={() => { onReviewChange?.(false); setDetail(detail === "generation" ? null : "generation"); }} />
    </div>
    {testedAt && !Number.isNaN(testedAt.getTime()) && <p className="apworld-evidence-date">Tested {new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(testedAt)}</p>}
    {reviewVisible && <div className="apworld-evidence-detail" role="region" aria-label="Security review explanation"><strong>Security review{version ? ` · v${version.version}` : ""}</strong><p>{reviewExplanation}</p>
      {review && <>
        <p>{review.method === "maintainer-decision" ? "Decision recorded" : "Source reviewed"} <time dateTime={review.reviewed_at}>{new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(review.reviewed_at))}</time> · {review.method === "maintainer-decision" ? "Human decision" : review.method === "source-review-with-qa" ? "Source review with independent QA" : "Automated source review"}</p>
        <p className="apworld-review-digest">Archive SHA-256: <code>{review.sha256}</code></p>
        <p><a href={review.record_url}>Public review record</a>. The full source report is private; this record contains its outcome, date and report fingerprint.</p>
      </>}
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => changeReview(false)}>Close explanation</button></div>}
    {detail === "generation" && (result ? <FuzzerModal result={result} version={version?.version} onClose={() => setDetail(null)} /> : <div className="apworld-evidence-detail" role="region" aria-label="Generation explanation"><p>{generationExplanation}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>)}
  </>;
}
