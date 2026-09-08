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
  if (!user) return open ? <button className="btn btn-sm" onClick={() => login(`/r/${roomId}`)}>Sign in to join room</button> : null;
  if (!open && !joined) return null;
  return <div>
    <button type="button" className="btn btn-sm" disabled={busy || loading} onClick={() => void toggle()}>
      {busy ? "Saving..." : joined ? "Leave room" : "Join room"}
    </button>
    <p className="muted" role="status">{joined ? "Joined. You can select this room in the YAML builder." : "Join now and send your YAML later."}</p>
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
