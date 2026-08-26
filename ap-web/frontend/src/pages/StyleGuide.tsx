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
          <button className="btn btn-primary">Primary action</button>
          <button className="btn">Secondary action</button>
          <a href="#components" className="sg-text-link">Explore components →</a>
        </div>
      </header>

      <nav className="sg-local-nav" aria-label="Style guide sections">
        <a href="#foundation">Foundation</a>
        <a href="#components">Components</a>
        <a href="#review">Review proposals</a>
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

        <div className="sg-type-specimen surface surface-spacious">
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
          <article className="surface">
            <span className="sg-label">Actions</span>
            <div className="sg-row">
              <button className="btn btn-primary">Create room</button>
              <button className="btn">View details</button>
              <button className="btn btn-quiet">Cancel</button>
            </div>
            <div className="sg-row">
              <button className="btn btn-icon" aria-label="Download example">↓</button>
              <a className="sg-text-link" href="#components">Read the setup guide →</a>
            </div>
          </article>

          <article className="surface">
            <span className="sg-label">Status and provenance</span>
            <div className="sg-row">
              <span className="badge badge-save">Community</span>
              <span className="badge badge-done">Verified</span>
              <span className="badge badge-progress">Review due</span>
              <span className="badge">Built in</span>
            </div>
            <p className="sg-provenance"><span>Reviewed 24 Aug 2026</span><span>Primary source</span><span>APWorld 1.2.3</span></p>
          </article>

          <article className="surface">
            <span className="sg-label">Fields</span>
            <label className="field"><span>Search integrations</span><input placeholder="Game or APWorld name…" /></label>
            <div className="field-pair">
              <label className="field"><span>Type</span><select defaultValue="all"><option value="all">All integrations</option><option>Built in</option><option>Community</option></select></label>
              <label className="field"><span>Version</span><input defaultValue="1.2.3" /></label>
            </div>
          </article>

          <article className="surface">
            <span className="sg-label">Feedback</span>
            <div className="notice notice-info"><strong>Version matters.</strong><span>Use the version selected by your host.</span></div>
            <div className="notice notice-success"><strong>Ready.</strong><span>Your player YAML is valid.</span></div>
            <div className="notice notice-warning"><strong>Not verified yet.</strong><span>No reviewed setup guide is recorded.</span></div>
          </article>
        </div>
      </section>

      <section id="review" className="sg-section sg-review-section">
        <div className="sg-section-heading">
          <span className="sg-review-flag">Needs review</span>
          <div><h2>Modules to approve before migration</h2><p>These four groups are visual proposals only. They are not shared production components yet.</p></div>
        </div>

        <div className="sg-review-grid">
          <article className="surface sg-review-card">
            <header className="sg-review-card-head"><div><span className="sg-label">01 · Navigation</span><h3>Tabs, filters and drawers</h3></div><span className="badge badge-progress">Proposal</span></header>
            <div className="sg-review-tabs" role="tablist" aria-label="Room sections">
              <button type="button" className="is-active" role="tab" aria-selected="true">Overview</button>
              <button type="button" role="tab" aria-selected="false">Players <span>12</span></button>
              <button type="button" role="tab" aria-selected="false">Activity</button>
            </div>
            <div className="sg-review-segments" aria-label="Catalog filter example">
              <button type="button" className="is-active">All games <span>616</span></button>
              <button type="button">Downloads <span>254</span></button>
              <button type="button">Built in <span>362</span></button>
            </div>
            <div className="sg-review-drawer">
              <div><strong>Room navigation</strong><small>Compact disclosure on narrow screens</small></div>
              <button type="button" className="btn btn-icon" aria-label="Open navigation menu">☰</button>
            </div>
          </article>

          <article className="surface sg-review-card">
            <header className="sg-review-card-head"><div><span className="sg-label">02 · Structured content</span><h3>Tables, grids and accordions</h3></div><span className="badge badge-progress">Proposal</span></header>
            <div className="sg-review-table-wrap">
              <table className="sg-review-table"><thead><tr><th>Player</th><th>Game</th><th>Status</th></tr></thead><tbody><tr><td>Appletini</td><td>Super Metroid</td><td><span className="badge badge-done">Ready</span></td></tr><tr><td>Berry</td><td>ANIMAL WELL</td><td><span className="badge badge-progress">Review</span></td></tr></tbody></table>
            </div>
            <details className="sg-review-accordion" open><summary><span>Submitted YAMLs</span><span>12 files</span></summary><div>Keep the summary scannable and place secondary detail inside the expanded region.</div></details>
            <details className="sg-review-accordion"><summary><span>Room activity</span><span>28 events</span></summary><div>Recent room events appear here.</div></details>
          </article>

          <article className="surface sg-review-card sg-review-card-wide">
            <header className="sg-review-card-head"><div><span className="sg-label">03 · Workspaces</span><h3>Dialogs, steppers and live tools</h3></div><span className="badge badge-progress">Proposal</span></header>
            <div className="sg-review-workspace">
              <div className="sg-review-dialog">
                <header><div><strong>Create player YAML</strong><small>Super Metroid · AP 0.6.7</small></div><button type="button" className="btn btn-icon" aria-label="Close example dialog">×</button></header>
                <ol className="sg-review-steps" aria-label="Builder progress"><li className="is-complete">Game</li><li className="is-active">Options</li><li>Review</li></ol>
                <div className="sg-review-option"><div><strong>Start inventory</strong><small>Choose the items available at the start.</small></div><button type="button" className="btn btn-sm">Configure</button></div>
                <footer><button type="button" className="btn btn-quiet">Back</button><button type="button" className="btn btn-primary">Review YAML</button></footer>
              </div>
              <aside className="sg-review-live"><span className="sg-label">Live preview</span><code>name: Appletini<br />game: Super Metroid<br />description: AP Pie preset</code><div className="notice notice-success"><strong>Ready.</strong><span>All required options are set.</span></div></aside>
            </div>
          </article>

          <article className="surface sg-review-card sg-review-card-wide">
            <header className="sg-review-card-head"><div><span className="sg-label">04 · Feedback and status</span><h3>Uploads, trackers, progress and toasts</h3></div><span className="badge badge-progress">Proposal</span></header>
            <div className="sg-review-feedback-grid">
              <button type="button" className="sg-review-dropzone"><strong>Drop a player YAML here</strong><span>or choose a file · YAML only · 8 MB maximum</span></button>
              <div className="sg-review-tracker"><div><span className="sg-review-player-mark">AP</span><div><strong>Appletini</strong><small>Super Metroid · Playing</small></div><span className="badge badge-done">Connected</span></div><div className="sg-review-progress"><span style={{ width: "68%" }} /></div><small>68 of 100 checks</small></div>
              <div className="sg-review-feed"><span className="sg-label">Activity</span><p><time>12:42</time><span><strong>Appletini</strong> found Morph Ball for Berry.</span></p><p><time>12:41</time><span><strong>Berry</strong> connected.</span></p></div>
              <div className="sg-review-toast" role="status"><span className="sg-review-toast-icon">✓</span><div><strong>YAML downloaded</strong><small>Appletini_Super_Metroid.yaml</small></div><button type="button" aria-label="Dismiss notification">×</button></div>
            </div>
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
          <div><h2>Current APWorld catalog item</h2><p>The live catalog pattern: compact identity, evidence-backed metadata and the actions available for the selected APWorld.</p></div>
        </div>
        <article className="apworld-card sg-apworld-example">
          <div className="apworld-card-badges"><span className="badge badge-save">Community</span></div>
          <div className="apworld-card-icon-tile" aria-hidden="true">AW</div>
          <div className="apworld-card-main">
            <header className="apworld-card-head">
              <div className="apworld-card-title"><h3>ANIMAL WELL</h3><code className="apworld-card-key">animal_well</code></div>
            </header>
            <div className="apworld-card-info-row">
              <dl className="apworld-card-meta">
                <div><dt>Versions</dt><dd>5 available</dd></div>
                <div><dt>Latest recorded</dt><dd>v0.5.4 <span className="fuzz-pill fuzz-pill-broken" title="Broken fuzz verdict"><span className="fuzz-pill-dot" /></span></dd></div>
                <div><dt>Setup</dt><dd>Reviewed details</dd></div>
              </dl>
              <div className="apworld-card-primary-actions">
                <button className="btn apworld-card-detail-button">View details</button>
                <button className="btn btn-sm">Create YAML</button>
                <button className="btn btn-sm apworld-download-btn" aria-label="Download example APWorld">↓</button>
              </div>
            </div>
            <div className="apworld-card-icons" aria-label="Recorded links">
              <a className="apworld-card-home" href="#apworld">github.com/ArchipelagoMW/Archipelago-ANIMAL-WELL</a>
            </div>
            <div className="apworld-card-tags"><span className="tag">adventure</span><span className="tag">metroidvania</span></div>
            <button type="button" className="apworld-version-toggle">View all 5 versions</button>
          </div>
        </article>
        <p className="sg-caption">This specimen uses the same structure and classes as the live `/apworlds` cards.</p>
      </section>
    </div>
  );
}
