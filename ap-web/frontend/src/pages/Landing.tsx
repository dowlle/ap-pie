import { useAuth } from "../context/AuthContext";

/**
 * Anonymous / pending-approval landing for the root route.
 *
 * - Unauthenticated visitors: see what Archipelago Pie does + a Discord login CTA.
 * - Logged-in but unapproved (closed-beta queue): same page, but the CTA
 *   becomes a "waiting for approval" notice that auto-flips when AuthContext
 *   polls and detects approval (then the parent route redirects to /rooms).
 *
 * Approved hosts and admins never see this - App.tsx routes them onward
 * before they hit Landing.
 */
export default function Landing() {
  const { user, login } = useAuth();
  const pending = !!user && !user.is_approved && !user.is_admin;

  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-hero-emoji" aria-hidden>🥧</div>
        <h1 className="landing-hero-title">Archipelago Pie</h1>
        <p className="landing-hero-tagline">
          A YAML collector and tracker for Archipelago multiworlds.
        </p>
        <p className="landing-hero-sub">
          Drop a link in your Discord, let everyone hand in their YAMLs in one place,
          and watch the run unfold from a single dashboard.
        </p>

        {pending ? (
          <div className="landing-pending">
            <strong>You're logged in as {user?.discord_username}.</strong>
            <span>
              Archipelago Pie is in <em>closed beta</em>, so room creation is gated. If you'd
              like to host rooms, ping <strong>Appie</strong> on Discord and I'll add you
              manually. You can already drop YAMLs in any room someone has shared with you
              - that part doesn't need approval. This page auto-refreshes once you're added.
            </span>
          </div>
        ) : (
          <div className="landing-cta">
            <button
              type="button"
              className="btn btn-primary landing-cta-btn"
              onClick={() => login("/")}
            >
              Sign in with Discord
            </button>
            <p className="landing-cta-hint">
              Archipelago Pie is in <strong>closed beta</strong>. Sign in to browse and submit
              to existing rooms straight away. If you'd like to host your own, ping
              <strong> Appie</strong> on Discord after signing in and I'll add you manually.
            </p>
          </div>
        )}
      </section>

      <section className="landing-features">
        <FeatureCard
          title="Collect YAMLs in one place"
          body="Spin up a room, share a single link with your group, and let players upload via drag-and-drop. No more chasing files in DMs."
        />
        <FeatureCard
          title="Validator that matches Archipelago"
          body="Every upload is checked against AP 0.6.7's actual generator rules - duplicate names, weighted game dicts, name-template tokens, the lot. Bad YAMLs surface before you hit Generate."
        />
        <FeatureCard
          title="Live progress tracker"
          body="Paste an archipelago.gg tracker URL and Archipelago Pie reads the WebSocket directly. Per-player checks, completion %, hints, and item flow on one dashboard."
        />
        <FeatureCard
          title="Claim mode for curated pools"
          body="Pre-load a stack of anonymous YAMLs and let logged-in players claim a slot of their choice. Per-player caps still apply, so nobody hoards."
        />
        <FeatureCard
          title="Resubmit with diffs"
          body="Players can re-upload the same YAML to fix it - Archipelago Pie shows a side-by-side diff so the host can see exactly what changed."
        />
        <FeatureCard
          title="Audited APWorld index"
          body="Pin per-game APWorld versions from a curated index. Every new entry runs through a sandboxed security audit before it lands, so what your players install isn't running unreviewed code."
        />
        <FeatureCard
          title="Generate locally"
          body="Download every YAML in the room as a single zip and run Archipelago on your own machine. Archipelago Pie stays out of your generation pipeline."
        />
      </section>

      <section className="landing-foot">
        <p>
          Built by <a href="https://github.com/dowlle" target="_blank" rel="noreferrer">@dowlle</a>{" "}
          for the Archipelago community. Open source on{" "}
          <a href="https://github.com/dowlle/ap-pie" target="_blank" rel="noreferrer">GitHub</a>.
        </p>
      </section>
    </div>
  );
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <article className="landing-feature">
      <h3>{title}</h3>
      <p>{body}</p>
    </article>
  );
}
