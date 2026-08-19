import { useAuth } from "../context/AuthContext";

/**
 * Anonymous / pending-approval landing for the root route.
 *
 * - Unauthenticated visitors: see what Archipelago Pie is + a Discord login CTA.
 * - Logged-in but unapproved (closed-beta queue): same page, but the CTA
 *   becomes a "waiting for approval" notice that auto-flips when AuthContext
 *   polls and detects approval (then the parent route redirects to /rooms).
 *
 * Approved hosts and admins never see this - App.tsx routes them onward
 * before they hit Landing.
 *
 * FEAT-39 design pass (ruled 2026-07-22): project-showcase layout from the
 * approved homepage mockup. Hero with the connected-islands motif, "Host a
 * room" as the primary CTA (the room collector remains the core utility),
 * Tools band above Projects. Digipelago stays off the page until it has
 * something releasable to show. The "ping Appie on Discord" host-access
 * flow copy is unchanged.
 */
export default function Landing() {
  const { user, login } = useAuth();
  const pending = !!user && !user.is_approved && !user.is_admin;

  return (
    <div className="lp">
      <section className="lp-hero">
        <svg className="lp-islands" viewBox="0 0 1200 420" fill="none" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <path d="M80 330 Q 300 240 520 300 T 900 260 T 1180 310" stroke="#3a3340" strokeDasharray="4 9" strokeWidth="1.5" />
          <path d="M150 120 Q 420 190 700 110 T 1120 160" stroke="#3a3340" strokeDasharray="4 9" strokeWidth="1.5" />
          <circle cx="80" cy="330" r="5" fill="#6da8c9" /><circle cx="520" cy="300" r="6" fill="#e8a857" />
          <circle cx="900" cy="260" r="5" fill="#7fa65a" /><circle cx="150" cy="120" r="5" fill="#e05d5d" />
          <circle cx="700" cy="110" r="6" fill="#6da8c9" /><circle cx="1120" cy="160" r="4" fill="#e8a857" />
        </svg>
        <span className="lp-kicker">Appie's Archipelago projects</span>
        <h1 className="lp-title">Your games, connected by <em>one randomizer.</em></h1>
        <p className="lp-sub">
          Learn Archipelago, organize a multiworld, or explore community game integrations.
        </p>
        <div className="lp-cta">
          <button type="button" className="btn btn-primary lp-btn" onClick={() => login("/")}>
            Create a collection room
          </button>
          <a href="/guides" className="btn lp-btn lp-btn-ghost">Start with the guides</a>
        </div>

        {pending && (
          <div className="landing-pending">
            <strong>You're logged in as {user?.discord_username}.</strong>
            <span>
              Archipelago Pie is in <em>closed beta</em>, so room creation is gated. If you'd
              like to host rooms, ping <strong>Appie</strong> on Discord and I'll add you
              manually. You can already drop YAMLs in any room someone has shared with you
              - that part doesn't need approval. This page auto-refreshes once you're added.
            </span>
          </div>
        )}
        {!user && (
          <p className="lp-hint">
            Archipelago Pie is in <strong>closed beta</strong>. Sign in with Discord to browse
            and submit to existing rooms straight away. To host your own, ping
            <strong> Appie</strong> on Discord after signing in.
          </p>
        )}
      </section>

      <div className="lp-wrap">
        <section className="lp-intro" aria-labelledby="what-is-archipelago">
          <span className="lp-k">Start here</span>
          <h2 id="what-is-archipelago">What is Archipelago?</h2>
          <p>
            <a href="https://archipelago.gg/" target="_blank" rel="noreferrer">Archipelago</a>{" "}
            is a randomizer that connects games. A location in your game can contain an item
            for somebody else's world, while an item you need may be waiting in theirs. Those
            worlds can use the same game or completely different supported games.
          </p>
          <p>You can play alone, join a room somebody else generated, or organize a multiworld for a group.</p>
          <div className="lp-paths">
            <a className="lp-path" href="/guides/getting-started">
              <span className="lp-k">New to Archipelago?</span>
              <h3>Choose how you want to play</h3>
              <p>Learn the basics, then follow the path for joining, playing solo, or organizing a group.</p>
              <span className="lp-path-link">Start with Archipelago →</span>
            </a>
            <button type="button" className="lp-path" onClick={() => login("/rooms")}>
              <span className="lp-k">Organizing a multiworld?</span>
              <h3>Collect each world's settings</h3>
              <p>Create a collection room where players can submit and check their configurations before generation.</p>
              <span className="lp-path-link">Create a collection room →</span>
            </button>
          </div>
        </section>

        <div className="lp-sect">Tools for every multiworld</div>
        <div className="lp-tools">
          <button type="button" className="lp-tool" onClick={() => login("/rooms")}>
            <span className="lp-k">Hosting</span>
            <h3>Collection rooms</h3>
            <p>Set a deadline and let players submit world configurations in the browser instead of chasing files in DMs.</p>
          </button>
          <a className="lp-tool" href="/guides">
            <span className="lp-k">Learn</span>
            <h3>Guides</h3>
            <p>From multiworld basics to per-game setup, written to get you playing fast.</p>
          </a>
          <a className="lp-tool" href="/apworlds">
            <span className="lp-k">Browse</span>
            <h3>APWorld index</h3>
            <p>The community catalog of game integrations, with per-version downloads.</p>
          </a>
        </div>

        <div className="lp-sect">Projects</div>
        <div className="lp-projects">
          <a className="lp-pj" style={{ "--c": "#e8a857" } as React.CSSProperties} href="/ctr">
            <span className="lp-st">Released</span>
            <div className="lp-glyph">CT</div>
            <h3>CTR Archipelago</h3>
            <p>The 1999 kart racer as a native PC randomizer. Warp pads, trophies, and relics join the pool.</p>
          </a>
          <article className="lp-pj" style={{ "--c": "#e05d5d" } as React.CSSProperties}>
            <span className="lp-st">Released</span>
            <div className="lp-glyph">PK</div>
            <h3>Pokepelago</h3>
            <p>A catching game in your browser where every Pokemon can carry someone's progression.</p>
          </article>
          <article className="lp-pj" style={{ "--c": "#7fa65a" } as React.CSSProperties}>
            <span className="lp-st">Alpha</span>
            <div className="lp-glyph">TB</div>
            <h3>Timberborn AP</h3>
            <p>Beaver colonies with a shuffled tech tree and faction-flavored progression.</p>
          </article>
        </div>
      </div>

      <section className="landing-foot">
        <p>
          Built by <a href="https://github.com/dowlle" target="_blank" rel="noreferrer">@dowlle</a>{" "}
          for the Archipelago community. Open source on{" "}
          <a href="https://github.com/dowlle/ap-pie" target="_blank" rel="noreferrer">GitHub</a>.
        </p>
        {/* Server-rendered page, so a plain anchor rather than a router Link. */}
        <p><a href="/privacy">Privacy</a></p>
      </section>
    </div>
  );
}
