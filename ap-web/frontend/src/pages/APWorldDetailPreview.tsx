import { Link, Navigate, useParams } from "react-router-dom";

type Preview = {
  name: string;
  identifier: string;
  type: "Built into Archipelago" | "Community integration";
  status: "Reviewed beta preview" | "Review blocked";
  statusTone: "reviewed" | "blocked";
  answer: string;
  facts: Array<{ label: string; value: string }>;
  notice?: { title: string; body: string };
  sections: Array<{ title: string; paragraphs: string[] }>;
  sourceHref: string;
  sourceLabel: string;
  reviewed: string;
  nextReview: string;
};

const PREVIEWS: Record<string, Preview> = {
  "super-metroid": {
    name: "Super Metroid Archipelago",
    identifier: "sm",
    type: "Built into Archipelago",
    status: "Reviewed beta preview",
    statusTone: "reviewed",
    answer: "Super Metroid is included with Archipelago 0.6.7, so this setup does not begin with a separate APWorld download. Prepare a legal base ROM and follow the official setup path for the client and generated patch.",
    facts: [
      { label: "Reviewed scope", value: "Archipelago 0.6.7" },
      { label: "APWorld download", value: "Not required" },
      { label: "Generated patch", value: ".apsm" },
    ],
    sections: [
      {
        title: "Before your multiworld is generated",
        paragraphs: [
          "The reviewed official guide expects an Archipelago installation, SNI, a legally obtained Super Metroid ROM and a suitable way to run the game. Detailed emulator and hardware choices remain with the official guide because that compatibility information can change between releases.",
          "Your player YAML describes the options for your world. It is sent to the host before generation; it does not install an APWorld or contain the playable game.",
        ],
      },
      {
        title: "After generation",
        paragraphs: [
          "The host returns a patch for your slot using the .apsm extension. Opening that patch starts the Super Metroid client workflow that creates the ROM used for the session.",
          "The reviewed source does not contain a completed Macintosh setup section. AP-Pie therefore does not turn that documentation gap into a broader platform-support claim.",
        ],
      },
    ],
    sourceHref: "https://archipelago.gg/tutorial/Super%20Metroid/multiworld_en",
    sourceLabel: "Open the official Super Metroid setup guide",
    reviewed: "24 August 2026",
    nextReview: "Next Archipelago release or 20 February 2027",
  },
  "animal-well": {
    name: "ANIMAL WELL Archipelago",
    identifier: "animal_well",
    type: "Community integration",
    status: "Review blocked",
    statusTone: "blocked",
    answer: "ANIMAL WELL uses a community APWorld rather than an integration bundled with Archipelago. Version 0.5.4 has source-controlled setup material, but AP-Pie is not recommending the package while its recorded fuzz verdict and base-game compatibility remain unresolved.",
    facts: [
      { label: "Reviewed package", value: "APWorld 0.5.4" },
      { label: "Minimum AP version", value: "0.6.4" },
      { label: "Base-game build", value: "Not source-stated" },
    ],
    notice: {
      title: "Download recommendation withheld",
      body: "The active catalog labels this integration stable while its 0.5.4 fuzz record says broken after 5,000 seeds. This preview keeps both signals visible instead of selecting the more convenient one.",
    },
    sections: [
      {
        title: "What the reviewed source establishes",
        paragraphs: [
          "The 0.5.4 release contains an animal_well.apworld package and declares Archipelago 0.6.4 as its minimum version. The maintainer guide places the package in Archipelago's custom-worlds location before player options are generated.",
          "The play workflow uses an ANIMAL WELL client while the game waits at its title screen. The guide also documents a Wine-based Linux route, but that does not establish a complete platform-support matrix.",
        ],
      },
      {
        title: "What remains unresolved",
        paragraphs: [
          "The reviewed manifest does not state a compatible ANIMAL WELL base-game build. A minimum Archipelago version is also not proof that every later release has been tested.",
          "Download and YAML Builder actions remain unavailable in this preview until the operational verdict, game-build scope and builder mapping have been reviewed.",
        ],
      },
    ],
    sourceHref: "https://github.com/ScipioWright/Archipelago-SW/blob/4b760c7/worlds/animal_well/docs/setup_en.md",
    sourceLabel: "Open the maintainer setup source",
    reviewed: "24 August 2026",
    nextReview: "On release or operational-verdict change",
  },
};

export default function APWorldDetailPreview() {
  const { slug = "" } = useParams();
  const preview = PREVIEWS[slug];
  if (!preview) return <Navigate to="/apworlds" replace />;

  return (
    <article className="apworld-detail-page">
      <header className="apworld-detail-hero">
        <div className="apworld-detail-title-row">
          <div>
            <h1>{preview.name}</h1>
            <code>{preview.identifier}</code>
          </div>
          <div className="apworld-detail-statuses">
            <span className="badge badge-builtin">{preview.type}</span>
            <span className={`review-badge review-badge-${preview.statusTone}`}>{preview.status}</span>
          </div>
        </div>
        <p className="apworld-detail-answer">{preview.answer}</p>
        <div className="apworld-detail-actions">
          <a className="btn btn-primary" href={preview.sourceHref} target="_blank" rel="noreferrer">{preview.sourceLabel}</a>
          <Link className="btn" to="/apworlds">Browse all APWorlds</Link>
        </div>
      </header>

      <dl className="apworld-detail-facts">
        {preview.facts.map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}
      </dl>

      {preview.notice && <aside className="review-notice review-notice-warning"><strong>{preview.notice.title}</strong><p>{preview.notice.body}</p></aside>}

      <div className="apworld-detail-layout">
        <div className="apworld-detail-content">
          {preview.sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </section>
          ))}
        </div>
        <aside className="apworld-detail-provenance">
          <h2>Review and sources</h2>
          <dl>
            <div><dt>Review state</dt><dd>{preview.status}</dd></div>
            <div><dt>Reviewed</dt><dd>{preview.reviewed}</dd></div>
            <div><dt>Review again</dt><dd>{preview.nextReview}</dd></div>
          </dl>
          <a href={preview.sourceHref} target="_blank" rel="noreferrer">Primary source ↗</a>
          <p>This beta page uses independently written AP-Pie copy derived from reviewed atomic claims.</p>
        </aside>
      </div>
    </article>
  );
}
