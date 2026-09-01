import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { getPublicRoom, type PublicRoom } from "../api";
import RoomDetail from "./RoomDetail";
import RoomPublic from "./RoomPublic";

/** Canonical room entry point. It resolves only session-relative capability
 * metadata from the privacy-filtered endpoint, then selects the host or
 * participant workspace. The host component still loads the authenticated
 * room API; public data never expands to include host-only fields. */
export default function RoomWorkspace() {
  const { id = "" } = useParams<{ id: string }>();
  const [room, setRoom] = useState<PublicRoom | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPublicRoom(id)
      .then((result) => { if (!cancelled) setRoom(result); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [id]);

  if (failed) return <RoomPublic />;
  if (!room) return <p className="loading" role="status">Loading room…</p>;
  return room.viewer_capabilities?.can_manage_room ? <RoomDetail /> : <RoomPublic />;
}

export function LegacyRoomRedirect() {
  const { id = "" } = useParams<{ id: string }>();
  return <Navigate to={`/r/${encodeURIComponent(id)}`} replace />;
}
