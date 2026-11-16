import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAPWorlds, type APWorldInfo, type APWorldVersion } from "../api";
import APWorldEvidence from "../components/APWorldEvidence";
import { applyPublicHead } from "../lib/publicHead";

function VersionDetails({ world, version }: { world: APWorldInfo; version: APWorldVersion }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const downloadable = world.downloadable_versions.some((item) => item.version === version.version);
  const buildable = world.builder_versions?.some((item) => item.version === version.version);
  const failed = version.security_review?.status === "fail";
  return <section className="apworld-detail-version" id={`version-${encodeURIComponent(version.version)}`}>
    <h2>Version {version.version}</h2>
    <APWorldEvidence version={version} builtin={world.is_builtin} />
    {(version.policy_hold || version.discovery?.held) && <aside className="review-notice review-notice-warning" role="note">
      <strong>Unresolved hold.</strong>{" "}
      {version.policy_hold?.summary ?? version.discovery?.policy_summary ?? "This release needs an explicit security or policy decision."}
    </aside>}
    <p className="apworld-review-digest">Archive SHA-256: {version.sha256 ? <code>{version.sha256}</code> : "Not recorded"}</p>
    {failed && <aside className="review-notice review-notice-warning">
      <strong>Security review failed</strong>
      <p>{version.security_review?.rationale ?? version.security_review?.summary}</p>
      <label className="apworld-detail-ack">
        <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
        I understand this release is not cleared by AP-Pie and I want to continue.
      </label>
    </aside>}
    <div className="apworld-detail-actions">
      {downloadable && (!failed || acknowledged) && <a className="btn" download href={`/api/apworlds/${encodeURIComponent(world.name)}/${encodeURIComponent(version.version)}/download`}>Download APWorld {version.version}</a>}
      {buildable && <Link className="btn" to={`/yaml-builder/${encodeURIComponent(world.name)}?version=${encodeURIComponent(version.version)}`}>Build YAML {version.version}</Link>}
    </div>
    {version.source === "builtin" && <p>Included with Archipelago; no separate APWorld download is required.</p>}
  </section>;
}

function WorldDetails({ world }: { world: APWorldInfo }) {
  const copy = world.editorial?.copy;
  useEffect(() => {
    applyPublicHead({
      title: world.detail_title ?? `${world.display_name} Archipelago APWorld | Archipelago Pie`,
      description: world.detail_description ?? `${world.display_name} for Archipelago: versions, downloads, setup links, and recorded security review and generation evidence.`,
      canonical: `https://ap-pie.com/apworlds/${world.detail_slug}`,
    });
  }, [world]);
  return <article className="apworld-detail-page">
    <header className="apworld-detail-hero">
      <div className="apworld-detail-title-row">
        <div><h1>{world.display_name} Archipelago</h1><code>{world.name}</code></div>
        <span className="badge">{world.is_builtin ? "Built into Archipelago" : "Community integration"}</span>
      </div>
      {copy && <p className="apworld-detail-answer">{copy.answer}</p>}
      <p>Catalog versions and recorded evidence are shown below. Missing evidence does not mean a release passed review or testing.</p>
      <div className="apworld-detail-actions">
        {world.setup_guide && <a className="btn btn-primary" href={world.setup_guide} target="_blank" rel="noreferrer">Setup guide</a>}
        {world.home && <a className="btn" href={world.home} target="_blank" rel="noreferrer">Project home</a>}
        {world.tracker && <a className="btn" href={world.tracker} target="_blank" rel="noreferrer">Tracker</a>}
        <Link className="btn" to="/apworlds">Browse all APWorlds</Link>
      </div>
    </header>
    <dl className="apworld-detail-facts">
      <div><dt>Stability reported by the index</dt><dd>{world.stability ?? "Not recorded"}</dd></div>
      <div><dt>Index entry updated</dt><dd>{world.updated_at ?? "Not recorded"}</dd></div>
      <div><dt>Versions recorded</dt><dd>{world.versions.length}</dd></div>
      {copy?.facts.map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}
    </dl>
    <p><a href="/guides/what-is-the-fuzzer">How to read security review and generation badges</a></p>
    {world.versions.map((version) => <VersionDetails key={`${world.name}@${version.version}`} world={world} version={version} />)}
    {world.versions.length === 0 && <p>No versions are recorded for this world.</p>}
    {copy && <div className="apworld-detail-layout">
      <div className="apworld-detail-content">{copy.sections.map((section) => <section key={section.title}>
        <h2>{section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
      </section>)}</div>
      <aside className="apworld-detail-provenance">
        <h2>Editorial review</h2>
        <p>Reviewed {world.editorial?.reviewed_at}. Review again {world.editorial?.next_review_at}.</p>
      </aside>
    </div>}
  </article>;
}

export default function APWorldDetailPreview() {
  const { slug = "" } = useParams();
  const [worlds, setWorlds] = useState<APWorldInfo[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    getAPWorlds().then((result) => { if (active) setWorlds(result); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);
  const world = worlds?.find((candidate) => candidate.detail_slug === slug);
  const override = world && world.detail_href !== `/apworlds/${slug}` ? world.detail_href : null;
  useEffect(() => { if (override) window.location.replace(override); }, [override]);
  if (error) return <p role="alert">The catalog could not be loaded. Please reload this page.</p>;
  if (worlds === null) return <p>Loading APWorld details…</p>;
  if (!world) return <article><h1>APWorld not found</h1><Link to="/apworlds">Browse all APWorlds</Link></article>;
  if (override) return <p>Opening game section…</p>;
  return <WorldDetails key={world.name} world={world} />;
}
