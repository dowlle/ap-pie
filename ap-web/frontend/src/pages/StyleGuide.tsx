const colors = [
  ["Canvas", "#121016", "Page background"],
  ["Surface", "#1b181f", "Cards and panels"],
  ["Raised", "#242029", "Interactive surfaces"],
  ["Border", "#332d39", "Quiet separation"],
  ["Text", "#f5f1eb", "Primary content"],
  ["Muted", "#a59c91", "Supporting content"],
  ["Amber", "#f2ad55", "Primary action"],
  ["Blue", "#72a7d8", "Information"],
  ["Green", "#69c99d", "Verified or stable"],
  ["Red", "#e57c78", "Error or destructive"],
];

export default function StyleGuide() {
  return (
    <div className="sg-page">
      <header className="sg-hero">
        <h1>One system, different kinds of work.</h1>
        <p>
          A warm, game-oriented interpretation of Raycast: calm surfaces, strong typography,
          compact controls and enough density for catalogs and multiworld tools.
        </p>
        <div className="sg-hero-actions">
          <button className="sg-button sg-button-primary">Primary action</button>
          <button className="sg-button sg-button-secondary">Secondary action</button>
          <a href="#components" className="sg-text-link">Explore components →</a>
        </div>
      </header>

      <nav className="sg-local-nav" aria-label="Style guide sections">
        <a href="#foundation">Foundation</a>
        <a href="#components">Components</a>
        <a href="#density">Page families</a>
        <a href="#apworld">APWorld example</a>
      </nav>

      <section id="foundation" className="sg-section">
        <div className="sg-section-heading">
          <div><h2>Familiar, warm and deliberate</h2><p>Consistent roles replace page-specific color and spacing choices.</p></div>
        </div>

        <div className="sg-color-grid">
          {colors.map(([name, value, purpose]) => (
            <div className="sg-color" key={name}>
              <span className="sg-color-swatch" style={{ background: value }} />
              <strong>{name}</strong><code>{value}</code><small>{purpose}</small>
            </div>
          ))}
        </div>

        <div className="sg-type-specimen sg-surface">
          <div className="sg-type-display">
            <span>Display · Bricolage Grotesque</span>
            <h2>Every world has a place.</h2>
          </div>
          <div className="sg-type-body">
            <span>Body and interface · Inter Tight</span>
            <h3>Crash Team Racing Archipelago</h3>
            <p>Find the right integration, match the host's version and follow a reviewed setup path.</p>
          </div>
          <div className="sg-type-mono">
            <span>Technical data · JetBrains Mono</span>
            <code>ctr_archipelago · v1.2.3 · sha256</code>
          </div>
        </div>
      </section>

      <section id="components" className="sg-section">
        <div className="sg-section-heading">
          <div><h2>A compact shared vocabulary</h2><p>The same controls and feedback patterns across public and signed-in pages.</p></div>
        </div>

        <div className="sg-component-grid">
          <article className="sg-surface">
            <span className="sg-label">Actions</span>
            <div className="sg-row">
              <button className="sg-button sg-button-primary">Create room</button>
              <button className="sg-button sg-button-secondary">View details</button>
              <button className="sg-button sg-button-quiet">Cancel</button>
            </div>
            <div className="sg-row">
              <button className="sg-icon-button" aria-label="Download example">↓</button>
              <a className="sg-text-link" href="#components">Read the setup guide →</a>
            </div>
          </article>

          <article className="sg-surface">
            <span className="sg-label">Status and provenance</span>
            <div className="sg-row">
              <span className="sg-badge sg-badge-blue">Community</span>
              <span className="sg-badge sg-badge-green">Verified</span>
              <span className="sg-badge sg-badge-amber">Review due</span>
              <span className="sg-badge">Built in</span>
            </div>
            <p className="sg-provenance"><span>Reviewed 24 Aug 2026</span><span>Primary source</span><span>APWorld 1.2.3</span></p>
          </article>

          <article className="sg-surface">
            <span className="sg-label">Fields</span>
            <label className="sg-field"><span>Search integrations</span><input placeholder="Game or APWorld name…" /></label>
            <div className="sg-field-pair">
              <label className="sg-field"><span>Type</span><select defaultValue="all"><option value="all">All integrations</option><option>Built in</option><option>Community</option></select></label>
              <label className="sg-field"><span>Version</span><input defaultValue="1.2.3" /></label>
            </div>
          </article>

          <article className="sg-surface">
            <span className="sg-label">Feedback</span>
            <div className="sg-notice sg-notice-info"><strong>Version matters.</strong><span>Use the version selected by your host.</span></div>
            <div className="sg-notice sg-notice-success"><strong>Ready.</strong><span>Your player YAML is valid.</span></div>
            <div className="sg-notice sg-notice-warning"><strong>Not verified yet.</strong><span>No reviewed setup guide is recorded.</span></div>
          </article>
        </div>
      </section>

      <section id="density" className="sg-section">
        <div className="sg-section-heading">
          <div><h2>Shared language, appropriate density</h2><p>Consistency does not mean forcing guides and workspaces into the same layout.</p></div>
        </div>
        <div className="sg-family-grid">
          <article className="sg-family sg-family-orientation"><h3>Clear story, few actions</h3><p>Homepage and project landing pages use generous rhythm and a strong next step.</p></article>
          <article className="sg-family sg-family-catalog"><h3>Fast scanning and comparison</h3><p>Catalog pages use compact filters, repeatable cards and predictable metadata.</p></article>
          <article className="sg-family sg-family-docs"><h3>Comfortable, source-backed reading</h3><p>Guides use a narrow measure, local navigation, callouts and provenance.</p></article>
          <article className="sg-family sg-family-workspace"><h3>Dense, responsive tools</h3><p>Builders and rooms prioritize state, controls and immediate feedback.</p></article>
        </div>
      </section>

      <section id="apworld" className="sg-section">
        <div className="sg-section-heading">
          <div><h2>Enough information, no invented certainty</h2><p>A visual hypothesis using only the narrow set of currently defensible fields.</p></div>
        </div>
        <article className="sg-apworld-card">
          <div className="sg-apworld-icon">AW</div>
          <div className="sg-apworld-main">
            <div className="sg-apworld-title"><div><h3>ANIMAL WELL</h3><code>animal_well</code></div><span className="sg-badge sg-badge-blue">Community</span></div>
            <div className="sg-apworld-meta"><span><small>Versions</small><strong>5 available</strong></span><span><small>Latest recorded</small><strong>v1.2.3</strong></span><span><small>Setup</small><strong>Review required</strong></span></div>
          </div>
          <div className="sg-apworld-actions"><button className="sg-button sg-button-secondary">View details</button><button className="sg-icon-button" aria-label="Download example APWorld">↓</button></div>
        </article>
        <p className="sg-caption">The final card fields remain subject to the APWorld information contract and evidence review.</p>
      </section>
    </div>
  );
}
