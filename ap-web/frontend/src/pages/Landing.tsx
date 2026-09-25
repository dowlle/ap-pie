import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useFeature } from "../context/FeaturesContext";

/**
 * Public landing for the root route.
 *
 * - Unauthenticated visitors: see what Archipelago Pie is + a Discord login CTA.
 * - Logged-in but unapproved while open access is disabled: same page, but
 *   the CTA becomes a waiting-for-approval notice.
 * - Signed-in members who can reach /rooms: same page, with every sign-in call
 *   to action replaced by a link into their own rooms and YAMLs.
 *
 * Admins still get GameList at the root; App.tsx routes them onward.
 *
 * FEAT-55 (2026-09-25): games directly under the hero with pictures, one row
 * of tasks, and the capability statement moved out of the hero into its own
 * block. Joining a room happens on the room page itself (Join room button),
 * so the homepage no longer asks for a pasted room link.
 */
export default function Landing() {
  const { user, login } = useAuth();
  const openRoomCreation = useFeature("open_room_creation");
  const pending = !!user && !user.is_approved && !user.is_admin && !openRoomCreation;
  // Mirrors RequireRoomAccess in App.tsx. Members who can reach /rooms get links
  // into their own area; everyone else keeps the sign-in call to action.
  const canUseRooms = !!user && (user.is_approved || user.is_admin || openRoomCreation);

  const organize = {
    kicker: "Organize",
    title: "Run a multiworld",
    text: "Open a collection room, share the link, and let players submit and check their YAMLs before you generate.",
  };

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
        <h1 className="lp-title">Your games, connected by <em>one randomizer.</em></h1>
        <p className="lp-sub">
          Learn Archipelago, make your player YAML, and organize multiworlds with your friends.
        </p>
        <div className="lp-cta">
          {canUseRooms ? (
            <>
              <Link className="btn btn-primary lp-btn" to="/rooms">Your rooms</Link>
              <Link className="btn lp-btn lp-btn-ghost" to="/my/yamls">Your YAMLs</Link>
            </>
          ) : (
            <>
              <a href="/guides/getting-started" className="btn btn-primary lp-btn">New to Archipelago? Start here</a>
              <button type="button" className="btn lp-btn lp-btn-ghost" onClick={() => login("/rooms")}>
                Organize a multiworld
              </button>
            </>
          )}
        </div>

        {pending && (
          <div className="landing-pending">
            <strong>You're logged in as {user?.discord_username}.</strong>
            <span>
              Archipelago Pie is in <em>closed beta</em>, so room creation is gated. If you'd
              like to create collection rooms, ping <strong>Appie</strong> on Discord and I'll add you
              manually. You can already drop YAMLs in any room someone has shared with you
              - that part doesn't need approval. This page auto-refreshes once you're added.
            </span>
          </div>
        )}
        {!user && !openRoomCreation && (
          <p className="lp-hint">
            Archipelago Pie is in <strong>closed beta</strong>. Sign in with Discord to browse
            and submit to existing collection rooms straight away. To create your own, ping
            <strong> Appie</strong> on Discord after signing in.
          </p>
        )}
      </section>

      <div className="lp-wrap">
        <div className="lp-sect">Games made here</div>
        <div className="lp-games">
          <a className="lp-game" style={{ "--c": "#e8a857" } as React.CSSProperties} href="/ctr">
            <picture>
              <source srcSet="/img/ctr/checks-feed.webp" type="image/webp" />
              <img src="/img/ctr/checks-feed.jpg" alt="CTR Archipelago: the Adventure hub while the on-screen feed lists items just found" width={1554} height={904} loading="lazy" />
            </picture>
            <div>
              <span className="lp-st">Released</span>
              <h3>CTR Archipelago</h3>
              <p>Crash Team Racing as a native PC randomizer. Warp pads ask for new things every seed, and your Trophies and Keys can come from anyone's game.</p>
              <span className="lp-pj-link">Explore CTR Archipelago <small>Download, setup and how it works</small></span>
            </div>
          </a>
          <div className="lp-game" style={{ "--c": "#e05d5d" } as React.CSSProperties}>
            <a href="/pokepelago" className="lp-game-cover" aria-hidden="true" tabIndex={-1}>
              <img src="/img/guides/pokepelago-gameplay.png" alt="" width={1200} height={630} loading="lazy" />
            </a>
            <div>
              <span className="lp-st">Released</span>
              <h3><a href="/pokepelago">Poképelago</a></h3>
              <p>Catch Pokémon by typing their names, right in your browser. In a multiworld, every catch can send someone their next item.</p>
              <span className="lp-game-links">
                <a href="https://pokepelago.ap-pie.com/">Play Poképelago</a>
                <a href="/pokepelago/setup">Setup guide</a>
              </span>
            </div>
          </div>
          <article className="lp-game lp-game-soon" style={{ "--c": "#7fa65a" } as React.CSSProperties}>
            <div>
              <span className="lp-st">In development</span>
              <h3>Timberborn Archipelago</h3>
              <p>Beaver colonies with a shuffled tech tree and faction-flavored progression.</p>
            </div>
          </article>
        </div>

        <div className="lp-sect">What do you want to do?</div>
        <div className="lp-tools lp-tools-four">
          <a className="lp-tool" href="/guides">
            <span className="lp-k">Learn</span>
            <h3>Read the guides</h3>
            <p>From multiworld basics to hosting and per-game setup.</p>
          </a>
          <a className="lp-tool" href="/yaml-builder">
            <span className="lp-k">Configure</span>
            <h3>Make a player YAML</h3>
            <p>Choose a game, set your options, and download a YAML for your host.</p>
          </a>
          {canUseRooms ? (
            <Link className="lp-tool" to="/rooms">
              <span className="lp-k">{organize.kicker}</span>
              <h3>{organize.title}</h3>
              <p>{organize.text}</p>
            </Link>
          ) : (
            <button type="button" className="lp-tool" onClick={() => login("/rooms")}>
              <span className="lp-k">{organize.kicker}</span>
              <h3>{organize.title}</h3>
              <p>{organize.text}</p>
            </button>
          )}
          <a className="lp-tool" href="/apworlds">
            <span className="lp-k">Browse</span>
            <h3>Find an APWorld</h3>
            <p>The community catalog of game integrations, with downloads per version.</p>
          </a>
        </div>
        <p className="lp-join-hint">Got a room link from your host? Open it and press <strong>Join room</strong> to add your YAMLs there.</p>

        <section className="lp-intro" aria-labelledby="what-is-archipelago">
          <span className="lp-k">Start here</span>
          <h2 id="what-is-archipelago">What is Archipelago?</h2>
          <p>
            <a href="https://archipelago.gg/" target="_blank" rel="noreferrer">Archipelago</a>{" "}
            is a randomizer that connects games. A location in your game can contain an item
            for somebody else's world, while an item you need may be waiting in theirs. Those
            worlds can use the same game or completely different supported games.
          </p>
          <p>
            <a href="/guides/getting-started">Getting started with Archipelago</a> explains how to
            join a group, play solo, or organize a multiworld.
          </p>
        </section>

        <section className="lp-intro lp-about" aria-labelledby="what-ap-pie-does">
          <h2 id="what-ap-pie-does">What Archipelago Pie does</h2>
          <p className="lp-capability">
            Archipelago Pie collects player YAMLs in a collection room, and gives you the reviewed APWorld catalog and a YAML Builder for making them.{" "}
            It does not generate the multiworld and does not run game servers: you generate locally with the Archipelago Launcher, then host the server on archipelago.gg or your own machine.
          </p>
          <p>
            Built by <a href="https://github.com/dowlle" target="_blank" rel="noreferrer">@dowlle</a> for the Archipelago community.
          </p>
        </section>
      </div>
    </div>
  );
}
