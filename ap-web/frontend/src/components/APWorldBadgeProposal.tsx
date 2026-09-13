import { useState } from "react";

type Tone = "pending" | "testing" | "passed" | "warning" | "failed";
type Evidence = { label: string; tone: Tone; explanation: string };

const security: Record<string, Evidence> = {
  pending: { label: "Review pending", tone: "pending", explanation: "This release has not completed a security review. It remains available to download; YAML Builder access waits for review and generation checks." },
  passed: { label: "Review passed", tone: "passed", explanation: "The security review found no issues in this exact release. This is a review result, not a guarantee that the package is safe." },
  warning: { label: "Review concerns", tone: "warning", explanation: "The review flagged behavior that needs a closer look. A flagged capability does not by itself establish malicious intent. Download remains available; Builder access waits for the concerns to be resolved." },
  failed: { label: "Review failed", tone: "failed", explanation: "The review identified a security issue in this release. Read the findings before deciding whether to download. YAML Builder access is unavailable until the issue is resolved or explicitly cleared." },
};
const generation: Record<string, Evidence> = {
  pending: { label: "Tests pending", tone: "pending", explanation: "Generation testing is queued. There is no generation result for this release yet. Download remains available." },
  testing: { label: "Generation testing", tone: "testing", explanation: "Generation tests are running. The badge will update when results are available; a running test is not a passing result." },
  passed: { label: "Generation passed", tone: "passed", explanation: "The standard configuration generated successfully and the recorded randomized generation tests passed. These checks do not test security or prove the game can be completed." },
  warning: { label: "Generation warnings", tone: "warning", explanation: "The standard configuration generated successfully, but some randomized option combinations failed. Builder access is available when security review and option parsing also pass. Test your group's actual YAMLs before playing." },
  failed: { label: "Generation failed", tone: "failed", explanation: "The standard configuration could not generate successfully. The release remains downloadable, but YAML Builder access is unavailable. An interrupted test or worker failure is not recorded as a game failure." },
};

function EvidenceBadge({ kind, evidence, onClick, expanded = false }: { kind: string; evidence: Evidence; onClick: () => void; expanded?: boolean }) {
  return <button type="button" className={`sg-evidence-badge is-${evidence.tone}`} title={evidence.explanation} aria-label={`${kind}: ${evidence.label}. Show explanation`} aria-expanded={expanded} onClick={onClick}><span className="sg-evidence-dot" aria-hidden="true" /><span>{evidence.label}</span></button>;
}

function ExampleCard({ title, initials, review, tests, ready, note, versions = false }: { title: string; initials: string; review: string; tests: string; ready: boolean; note: string; versions?: boolean }) {
  const [older, setOlder] = useState(false);
  const [detail, setDetail] = useState<"security" | "generation" | "download" | "builder" | null>(null);
  const needsExplanation = !older && (review !== "passed" || tests !== "passed");
  const sec = { ...security[older ? "passed" : review] };
  const gen = { ...generation[older ? "passed" : tests] };
  if (needsExplanation && review !== "passed") sec.explanation = note + " " + sec.explanation;
  if (needsExplanation && tests !== "passed") gen.explanation = note + " " + gen.explanation;
  const concerns = sec.tone === "warning" || sec.tone === "failed";
  const builderReady = older || ready || versions;
  const version = older ? "1.1.0" : "1.2.0";
  const builderVersion = versions ? "1.1.0" : version;
  const blocker = review !== "passed" ? "Builder after review" : "Builder after tests";
  return (
    <article className="apworld-card sg-evidence-card">
      <div className="apworld-card-icon-tile" aria-hidden="true">{initials}</div>
      <div className="apworld-card-main">
        <header className="apworld-card-head"><div className="apworld-card-title"><h3>{title}</h3><span className="sg-evidence-community">Community</span><span className="sg-evidence-version">v{version} · {older ? "Previous release" : "Latest release"}</span></div></header>
        <div className="sg-evidence-pair">
          <EvidenceBadge kind="Security" evidence={sec} expanded={detail === "security"} onClick={() => setDetail(detail === "security" ? null : "security")} />
          <EvidenceBadge kind="Generation" evidence={gen} expanded={detail === "generation"} onClick={() => setDetail(detail === "generation" ? null : "generation")} />
        </div>
        <p className="sg-evidence-freshness">{older ? "Checked 10 Sep 2026" : review === "pending" ? "Discovered 13 Sep 2026" : "Checked 13 Sep 2026"}</p>
        {needsExplanation && <p className="sg-evidence-note">{note}</p>}
        <div className="sg-evidence-actions">
          {concerns && <button type="button" className="btn btn-primary btn-sm" onClick={() => setDetail("security")}>Read findings</button>}
          <button type="button" className={`btn ${concerns ? "" : "btn-primary"} btn-sm`} onClick={() => setDetail(detail === "download" ? null : "download")}>Download <span aria-hidden="true">↗</span></button>
          {builderReady ? <button type="button" className="btn btn-sm" onClick={() => setDetail(detail === "builder" ? null : "builder")}>{versions ? `Create YAML · ${builderVersion}` : "Create YAML"}</button> : <span className="sg-evidence-blocker" title="Builder access waits for security clearance, readable options and successful standard generation.">{blocker}</span>}
        </div>
        {versions && <details className="sg-evidence-versions"><summary>Other versions</summary><label className="sg-evidence-select"><span>Choose version</span><select value={older ? "older" : "latest"} onChange={(e) => { setOlder(e.target.value === "older"); setDetail(null); }}><option value="latest">1.2.0 · Latest release · Review and tests pending</option><option value="older">1.1.0 · Previous release · Builder ready</option></select></label></details>}
        {detail && <div className="sg-evidence-detail" role="region" aria-label={`${title} evidence explanation`}><strong>{detail === "security" ? `Security review · v${version}` : detail === "generation" ? `Generation · v${version}` : detail === "download" ? `Upstream download · v${version}` : `Builder ready · v${builderVersion}`}</strong><p>{detail === "security" ? sec.explanation : detail === "generation" ? gen.explanation : detail === "download" ? "In the catalog, this action opens the upstream release download, usually on GitHub. Downloads remain available when checks are pending or show warnings. This style-guide example does not download a file." : `Review, option parsing and standard generation passed for v${builderVersion}. This style-guide example does not create a YAML.`}</p><button type="button" className="btn btn-quiet btn-sm" onClick={() => setDetail(null)}>Close explanation</button></div>}
      </div>
    </article>
  );
}

export default function APWorldBadgeProposal() {
  const [selected, setSelected] = useState<{ kind: string; evidence: Evidence } | null>(null);
  return (
    <section id="apworld-badges" className="sg-section sg-evidence-proposal">
      <div className="sg-section-heading"><span className="sg-review-flag is-proposed">Proposed</span><h2>Every release. Clear evidence.</h2><p>Download the newest release while checks catch up. Security review and generation testing each have their own badge.</p></div>
      <div className="sg-evidence-vocabulary">
        {[{ kind: "Security review", states: security }, { kind: "Generation testing", states: generation }].map(({ kind, states }) => <article className="surface" key={kind}><span className="sg-label">{kind}</span><div className="sg-evidence-specimens">{Object.entries(states).map(([key, evidence]) => <EvidenceBadge key={key} kind={kind} evidence={evidence} expanded={selected?.evidence === evidence} onClick={() => setSelected(selected?.evidence === evidence ? null : { kind, evidence })} />)}</div><p className="sg-evidence-note">{kind === "Security review" ? "A green review result means no issues were found, not a safety guarantee." : "Generation checks test seed creation, not security or a complete playthrough."}</p></article>)}
      </div>
      {selected && <div className="sg-evidence-detail sg-evidence-vocabulary-detail" role="region" aria-label="Badge explanation"><strong>{selected.kind} · {selected.evidence.label}</strong><p>{selected.evidence.explanation}</p></div>}
      <div className="sg-evidence-example-heading"><div><h3>How they read in the catalog</h3><p>Illustrative games, versions and results. Click a badge to inspect its meaning.</p></div><span className="badge">Sample data</span></div>
      <div className="sg-evidence-cards">
        <ExampleCard title="Mystery World" initials="MW" review="pending" tests="pending" ready={false} note="The latest release awaits review and tests. Create YAML uses reviewed version 1.1.0." versions />
        <ExampleCard title="Racing World" initials="RW" review="passed" tests="passed" ready note="Review, option parsing and generation checks passed for this version." />
        <ExampleCard title="Action World" initials="AC" review="warning" tests="passed" ready={false} note="Review flagged game-launching behavior. Read the findings before downloading." />
        <ExampleCard title="Adventure World" initials="AD" review="passed" tests="warning" ready note="Standard settings generate. Some randomized option combinations failed." />
      </div>
      <article className="surface sg-evidence-builtin"><div><span className="badge badge-builtin">Built in</span><h3>Built-in games get a Builder too.</h3><p>Super Metroid · Archipelago 0.6.7. Choose game options without downloading a separate APWorld.</p><p className="sg-evidence-note">Options come from the official release template. Being built in is source information; it does not substitute for a security or generation result.</p></div><a className="btn btn-primary btn-sm" href="/yaml-builder/sm?version=0.6.7">Create Super Metroid YAML →</a></article>
      <p className="sg-caption">Badges belong to the selected release. New versions start pending; older results stay with the version that was checked. Builder access requires security clearance, readable options and successful standard generation.</p>
    </section>
  );
}
