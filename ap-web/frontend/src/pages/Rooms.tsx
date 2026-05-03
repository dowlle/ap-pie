import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getRooms, createRoom, type Room } from "../api";
import { useAuth } from "../context/AuthContext";
import { localInputValueToIso } from "../lib/roomDeadline";

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

function CreateRoomForm({ onCreated }: { onCreated: () => void }) {
  const { user } = useAuth();
  const [show, setShow] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [spoiler, setSpoiler] = useState(3);
  const [race, setRace] = useState(false);
  const [requireDiscordLogin, setRequireDiscordLogin] = useState(false);
  const [deadlineLocal, setDeadlineLocal] = useState("");
  const [error, setError] = useState("");

  const hostName = user?.discord_username ?? "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !hostName.trim()) return;
    setError("");
    try {
      await createRoom({
        name: name.trim(),
        host_name: hostName,
        description,
        spoiler_level: spoiler,
        race_mode: race,
        require_discord_login: requireDiscordLogin,
        submit_deadline: localInputValueToIso(deadlineLocal),
      });
      setName("");
      setDescription("");
      setRequireDiscordLogin(false);
      setDeadlineLocal("");
      setShow(false);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };

  if (!show) {
    return <button className="btn btn-primary" onClick={() => setShow(true)}>Create Room</button>;
  }

  return (
    <form onSubmit={handleSubmit} className="create-room-form">
      <input placeholder="Room name" value={name} onChange={(e) => setName(e.target.value)} required />
      {hostName && (
        <p className="muted" style={{ margin: "0.25rem 0" }}>
          Hosting as <strong>{hostName}</strong>
        </p>
      )}
      <textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} />
      <div className="form-row">
        <label>Spoiler level:
          <select value={spoiler} onChange={(e) => setSpoiler(Number(e.target.value))}>
            <option value={0}>None</option>
            <option value={1}>Basic</option>
            <option value={2}>Playthrough</option>
            <option value={3}>Full</option>
          </select>
        </label>
        <label>
          <input type="checkbox" checked={race} onChange={(e) => setRace(e.target.checked)} />
          Race mode
        </label>
        <label title="Players must log in with Discord before they can submit a YAML to this room. Lets you see who uploaded what.">
          <input
            type="checkbox"
            checked={requireDiscordLogin}
            onChange={(e) => setRequireDiscordLogin(e.target.checked)}
          />
          Require Discord login
        </label>
      </div>
      <div className="form-row">
        <label title="Optional. The room auto-closes at this date/time in your local timezone. You can still close it manually before then.">
          Auto-close at:
          <input
            type="datetime-local"
            value={deadlineLocal}
            onChange={(e) => setDeadlineLocal(e.target.value)}
            style={{ marginLeft: "0.5rem" }}
          />
        </label>
        {deadlineLocal && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setDeadlineLocal("")}
            title="Clear the auto-close deadline"
          >
            Clear
          </button>
        )}
      </div>
      <div className="form-row">
        <button type="submit" className="btn btn-primary" disabled={!hostName}>Create</button>
        <button type="button" className="btn" onClick={() => setShow(false)}>Cancel</button>
      </div>
      {error && <span className="upload-error">{error}</span>}
    </form>
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
        {!isViewingAsOther && <CreateRoomForm onCreated={refresh} />}
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
