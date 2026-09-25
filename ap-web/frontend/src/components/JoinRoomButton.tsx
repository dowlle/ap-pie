import { useEffect, useState } from "react";
import { getMyRooms, setRoomMembership } from "../api";
import { useAuth } from "../context/AuthContext";

export default function JoinRoomButton({ roomId, open }: { roomId: string; open: boolean }) {
  const { user, login } = useAuth();
  const userId = user?.id;
  const [joined, setJoined] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    if (userId === undefined) return;
    getMyRooms().then((rooms) => { if (!cancelled) setJoined(rooms.some((room) => room.id === roomId && room.joined)); })
      .catch(() => { if (!cancelled) setError("Could not check room membership."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [roomId, userId]);
  const toggle = async () => {
    setBusy(true); setError("");
    try { await setRoomMembership(roomId, !joined); setJoined(!joined); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not join room"); }
    finally { setBusy(false); }
  };
  if (!user) return open ? <div className="join-room"><button className="btn btn-primary" onClick={() => login(`/r/${roomId}`)}>Sign in to join room</button><p className="muted">Joining keeps this room in your list, so you can add YAMLs to it now or later.</p></div> : null;
  if (!open && !joined) return null;
  return <div className="join-room">
    <button type="button" className={joined ? "btn btn-sm" : "btn btn-primary"} disabled={busy || loading} onClick={() => void toggle()}>
      {busy ? "Saving..." : joined ? "Leave room" : "Join room"}
    </button>
    <p className="muted" role="status">{joined ? "Joined. Add your YAML below, now or later; the YAML Builder also lists this room." : "Joining keeps this room in your list, so you can add YAMLs to it now or later."}</p>
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
