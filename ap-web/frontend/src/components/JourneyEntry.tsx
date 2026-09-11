import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function JourneyEntry() {
  const [invitation, setInvitation] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { user, login } = useAuth();
  return <section id="choose-your-path" className="journey-entry" aria-label="What would you like to do?">
    <form onSubmit={(event) => {
      event.preventDefault();
      try {
        const url = new URL(invitation.trim(), location.origin);
        if (![location.host, "ap-pie.com", "beta.ap-pie.com"].includes(url.host) || !/^\/r\/[a-zA-Z0-9_-]+\/?$/.test(url.pathname)) throw new Error();
        navigate(url.pathname);
      } catch { setError("Paste the collection-room link your host shared, ending in /r/ followed by the room ID."); }
    }}>
      <h2>Join a room</h2><p>Start with your host's requirements and submit there.</p>
      <label>Collection-room link<input type="text" value={invitation} placeholder="https://ap-pie.com/r/…" onChange={e => setInvitation(e.target.value)} /></label>
      <button className="btn" type="submit">Open invitation</button>
      {error && <p role="alert">{error}</p>}
    </form>
    <article><h2>Prepare my YAML</h2><p>Choose your options and save your setup to continue on another device.</p><Link className="btn" to="/yaml-builder">Prepare a YAML</Link></article>
    <article><h2>Organize a multiworld</h2><p>Collect player YAMLs, review submissions, then generate with your chosen Archipelago installation.</p>{user ? <Link className="btn" to="/rooms">Create or manage a collection room</Link> : <button type="button" className="btn" onClick={() => login("/rooms")}>Sign in to organize a room</button>}</article>
  </section>;
}
