import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getRooms, type Room } from "../api";
import { useAuth } from "../context/AuthContext";
import CreateRoomModal from "../components/CreateRoomModal";

function statusBadge(status: string) {
  const cls =
    status === "open" ? "badge-save" :
    status === "closed" ? "badge-progress" :
    status === "generating" ? "badge-progress" :
    status === "generated" ? "badge-done" :
    status === "playing" ? "badge-done" :
    "";
  return <span className={`badge ${cls}`}>{status}</span>;
}

function CreateRoomButton({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="btn btn-primary" onClick={() => setOpen(true)}>Create Room</button>
      <CreateRoomModal
        open={open}
        onClose={() => setOpen(false)}
        onCreated={onCreated}
      />
    </>
  );
}

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Open", value: "open" },
  { label: "Playing", value: "playing" },
  { label: "Completed", value: "generated" },
];

export default function Rooms() {
  const { user } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Admins can use ?as_user=<id> to view another user's rooms (FEAT-03).
  // Non-admins are silently forced to their own list server-side, so this
  // param is admin-only by design.
  const asUserParam = searchParams.get("as_user");
  const asUser = asUserParam ? Number(asUserParam) : undefined;
  const isViewingAsOther = !!user?.is_admin && asUser !== undefined;

  const refresh = () => {
    setLoading(true);
    getRooms(statusFilter || undefined, asUser)
      .then(setRooms)
      .finally(() => setLoading(false));
  };

  useEffect(() => { refresh(); }, [statusFilter, asUser]);

  // The viewed user's display name, derived from any room's host_name when
  // possible. If the user has no rooms, we don't have it server-side from
  // this page alone - the admin originally clicked "View rooms" from the
  // Admin page so they know who they were targeting.
  const viewedHostName = isViewingAsOther
    ? rooms[0]?.host_name ?? `user #${asUser}`
    : null;

  return (
    <div>
      <div className="page-header">
        <h1>Rooms</h1>
        {!isViewingAsOther && <CreateRoomButton onCreated={refresh} />}
      </div>

      {isViewingAsOther && (
        <div className="approval-toast" role="status" style={{ marginBottom: "1rem" }}>
          <span>
            Viewing rooms as <strong>{viewedHostName}</strong> (admin override).
          </span>
          <Link to="/rooms" className="btn btn-sm">View my own rooms</Link>
        </div>
      )}

      <div className="market-tabs">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value}
            className={`btn btn-sm${statusFilter === t.value ? " btn-primary" : ""}`}
            onClick={() => setStatusFilter(t.value)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="loading">Loading...</p>
      ) : rooms.length === 0 ? (
        <p className="empty">{
          isViewingAsOther
            ? `No rooms for this user${statusFilter ? ` (status: ${statusFilter})` : ""}.`
            : statusFilter
              ? `No ${statusFilter} rooms.`
              : "No rooms yet. Create one to get started!"
        }</p>
      ) : (
        <div className="table-wrapper">
          <table className="game-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Host</th>
                <th>Status</th>
                <th>Players</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => navigate(`/rooms/${r.id}`)}>
                  <td>{r.name}</td>
                  <td>{r.host_name}</td>
                  <td>{statusBadge(r.status)}</td>
                  <td>{r.yamls?.length ?? "-"}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
