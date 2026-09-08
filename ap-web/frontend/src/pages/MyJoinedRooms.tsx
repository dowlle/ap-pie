import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMyRooms, setRoomMembership, type MyRoom } from "../api";

export default function MyJoinedRooms() {
  const [rooms, setRooms] = useState<MyRoom[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getMyRooms().then((items) => { if (!cancelled) setRooms(items); })
      .catch(() => { if (!cancelled) setError("Could not load rooms."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  const leave = async (id: string) => {
    setBusy(true); setError("");
    try { setRooms(await setRoomMembership(id, false)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not leave room"); }
    finally { setBusy(false); }
  };
  return <section className="settings-section">
    <h2>My rooms</h2>
    <p>Open a host's shared room link and choose “Join room”. You can send a YAML later from the builder.</p>
    {error && <p role="alert" className="error">{error}</p>}
    {loading ? <p>Loading rooms...</p> : rooms.length === 0 ? <p>You haven't joined any rooms yet.</p> :
      <div className="favorite-games-grid">{rooms.map((room) => <article className="favorite-game-card" key={room.id}>
        <h3><Link to={`/r/${room.id}`}>{room.name}</Link></h3>
        <p>{room.status}{room.is_host ? " · Hosted by you" : ""}</p>
        <div className="favorite-game-actions">
          <Link className="btn btn-sm" to={`/r/${room.id}`}>Open room</Link>
          {room.status === "open" && <Link className="btn btn-sm btn-primary" to="/yaml-builder">Build a YAML</Link>}
          {room.joined && <button className="btn btn-sm" disabled={busy} onClick={() => void leave(room.id)}>Leave room</button>}
        </div>
      </article>)}</div>}
    <p className="muted">Leaving removes your saved membership. YAMLs you already submitted remain in the room.</p>
  </section>;
}
