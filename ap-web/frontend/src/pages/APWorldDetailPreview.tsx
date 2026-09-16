import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { getAPWorlds, type APWorldInfo, type FuzzResult } from "../api";

type ReviewStatus = "pass" | "needs_review" | "fail" | "held" | "human_accepted";

const REVIEW_LABELS: Record<ReviewStatus, string> = {
  pass: "Review passed",
  needs_review: "Review concerns",
  fail: "Review failed",
  held: "Review held",
  human_accepted: "Concerns accepted",
};

function reviewTone(status: ReviewStatus): string {
  if (status === "pass") return "passed";
  if (status === "fail") return "failed";
  return "warning";
}

function generationTone(result: FuzzResult): string {
  const warnings = result.verdict !== "clean" || result.default_rate > 0 || result.worst_hook_rate > 0;
  return warnings ? "warning" : "passed";
}

function generationLabel(result: FuzzResult): string {
  const warnings = result.verdict !== "clean" || result.default_rate > 0 || result.worst_hook_rate > 0;
  return warnings ? "Generation warnings" : "Generation passed";
}

function formatDate(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(parsed);
}

function percent(rate: number): string {
  return `${(rate * 100).toFixed(rate > 0 && rate < 0.001 ? 2 : 1)}%`;
}

export default function APWorldDetailPreview() {
  const { slug = "" } = useParams();
  const [worlds, setWorlds] = useState<APWorldInfo[] | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);

  useEffect(() => {
    getAPWorlds().then(setWorlds).catch(() => setWorlds([]));
  }, []);

  const world = useMemo(
    () => worlds?.find((candidate) => candidate.editorial?.slug === slug),
    [worlds, slug],
  );

  // Route overrides are server-rendered documents (for example CTR owns
  // /ctr). Leave the SPA with a full navigation rather than a client route.
  useEffect(() => {
    if (world?.editorial?.route_override && world.editorial.route_kind === "server") {
      window.location.replace(world.editorial.route_override);
    }
  }, [world]);

  if (worlds === null) {
    return <p className="apworld-detail-loading">Loading reviewed page…</p>;
  }
  if (!world || !world.editorial) return <Navigate to="/apworlds" replace />;
  if (world.editorial.route_override) return <Navigate to={world.editorial.route_override} replace />;

  const copy = world.editorial.copy;
  const latestVersion = world.downloadable_versions[0]?.version;
  const indexedVersion = world.versions.find((version) => version.version === latestVersion) ?? world.versions[0];
  const review = indexedVersion?.security_review ?? null;
  const generation = indexedVersion?.fuzz_result ?? null;

  const downloadHref = indexedVersion
    ? `/api/apworlds/${encodeURIComponent(world.name)}/${encodeURIComponent(indexedVersion.version)}/download`
    : undefined;
  const builderHref = indexedVersion
    ? `/yaml-builder/${encodeURIComponent(world.name)}?version=${encodeURIComponent(indexedVersion.version)}`
    : undefined;
  const sourceHref = world.setup_guide || world.home;
  const sourceLabel = world.setup_guide ? "Open the setup source" : "Open the project page";
  const blocked = review?.status === "fail";

  return (
    <article className="apworld-detail-page">
      <header className="apworld-detail-hero">
        <div className="apworld-detail-title-row">
          <div>
            <h1>{world.display_name}</h1>
            <code>{world.name}</code>
          </div>
          <div className="apworld-detail-statuses">
            <span className="badge">{world.is_builtin ? "Built into Archipelago" : "Community integration"}</span>
            <span className="review-badge review-badge-reviewed">
              {world.editorial.beta_preview_only ? "Reviewed beta preview" : "Reviewed"}
            </span>
          </div>
        </div>
        {copy && <p className="apworld-detail-answer">{copy.answer}</p>}
        <div className="apworld-detail-actions">
          {sourceHref && <a className="btn btn-primary" href={sourceHref} target="_blank" rel="noreferrer">{sourceLabel}</a>}
          {downloadHref && !blocked && (
            <a className="btn" href={downloadHref} download>Download APWorld {indexedVersion?.version}</a>
          )}
          {builderHref && <Link className="btn" to={builderHref}>Build YAML</Link>}
          <Link className="btn" to="/apworlds">Browse all APWorlds</Link>
        </div>
      </header>

      <div className="apworld-evidence-pair">
        <span className={`apworld-evidence-badge is-${review ? reviewTone(review.status) : "pending"}`}>
          <span aria-hidden="true" />{review ? REVIEW_LABELS[review.status] : "Review pending"}
        </span>
        <span className={`apworld-evidence-badge is-${generation ? generationTone(generation) : "pending"}`}>
          <span aria-hidden="true" />{generation ? generationLabel(generation) : "Tests pending"}
        </span>
      </div>
      {generation && <p className="apworld-evidence-date">Tested {formatDate(generation.fuzzed_at)}</p>}

      {copy && copy.facts.length > 0 && (
        <dl className="apworld-detail-facts">
          {copy.facts.map((fact) => (
            <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>
          ))}
        </dl>
      )}

      {blocked && review && (
        <aside className="review-notice review-notice-warning">
          <strong>Security review failed</strong>
          <p>{review.rationale ?? review.summary}</p>
          <label className="apworld-detail-ack">
            <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
            I understand this release is not cleared by AP-Pie and I want to continue to the upstream source.
          </label>
          {acknowledged && downloadHref && (
            <p><a className="btn" href={downloadHref} download>Continue to APWorld {indexedVersion?.version}</a></p>
          )}
        </aside>
      )}

      {(generation || review) && (
        <div className="apworld-detail-evidence">
          <section>
            <h2>Generation result</h2>
            {generation ? (
              <dl>
                <div><dt>Verdict</dt><dd>{generation.verdict}</dd></div>
                <div><dt>Default seed runs</dt><dd>{generation.seeds.toLocaleString("en-GB")}</dd></div>
                <div><dt>Failure rate</dt><dd>{percent(generation.default_rate)}</dd></div>
                {generation.worst_hook && <div><dt>Worst hook</dt><dd>{generation.worst_hook} ({percent(generation.worst_hook_rate)})</dd></div>}
                <div><dt>Checked</dt><dd>{formatDate(generation.fuzzed_at)}</dd></div>
              </dl>
            ) : (
              <p>No generation test result is recorded for this release yet.</p>
            )}
          </section>
          <section>
            <h2>Security review result</h2>
            {review ? (
              <>
                <dl>
                  <div><dt>Status</dt><dd>{REVIEW_LABELS[review.status]}</dd></div>
                  <div><dt>Method</dt><dd>{review.method === "maintainer-decision" ? "Human decision" : review.method === "source-review-with-qa" ? "Source review with independent QA" : "Automated source review"}</dd></div>
                  <div><dt>Reviewed</dt><dd>{formatDate(review.reviewed_at)}</dd></div>
                  <div><dt>Scope</dt><dd>exact {indexedVersion?.version} bytes</dd></div>
                </dl>
                <p>{review.summary}</p>
                {review.sha256 && <p className="apworld-review-digest">Archive SHA-256: <code>{review.sha256}</code></p>}
                {review.record_url && <p><a href={review.record_url}>Public review record</a>. The full source report is private; this record carries its outcome, date and report fingerprint.</p>}
              </>
            ) : (
              <p>No matching security review is recorded for these exact release bytes. This is not a safety clearance.</p>
            )}
          </section>
        </div>
      )}

      <div className="apworld-detail-layout">
        <div className="apworld-detail-content">
          {copy?.sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </section>
          ))}
        </div>
        <aside className="apworld-detail-provenance">
          <h2>Review and sources</h2>
          <dl>
            <div><dt>Review state</dt><dd>{world.editorial.beta_preview_only ? "Reviewed beta preview" : "Reviewed"}</dd></div>
            <div><dt>Reviewed</dt><dd>{formatDate(world.editorial.reviewed_at)}</dd></div>
            <div><dt>Review again</dt><dd>{formatDate(world.editorial.next_review_at)}</dd></div>
          </dl>
          {sourceHref && <a href={sourceHref} target="_blank" rel="noreferrer">Primary source ↗</a>}
          <p>Independently written AP-Pie copy, approved from the version-controlled editorial record.</p>
        </aside>
      </div>
    </article>
  );
}
