import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getRooms, type Room } from "../api";

export default function Tracker() {
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([getRooms("playing"), getRooms("generated")])
      .then(([playing, generated]) => setRooms([...playing, ...generated]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1>Tracker</h1>
      <p className="muted" style={{ marginBottom: "1rem" }}>
        Live item tracking for active and recently played games.
      </p>

      {loading ? (
        <p className="loading">Loading...</p>
      ) : rooms.length === 0 ? (
        <p className="empty">No active games to track. Launch a server from a room to get started.</p>
      ) : (
        <div className="table-wrapper">
          <table className="game-table">
            <thead>
              <tr>
                <th>Room</th>
                <th>Host</th>
                <th>Status</th>
                <th>Players</th>
              </tr>
            </thead>
            <tbody>
              {rooms.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => navigate(`/rooms/${r.id}`)}>
                  <td>{r.name}</td>
                  <td>{r.host_name}</td>
                  <td>
                    <span className={`badge ${r.status === "playing" ? "badge-done" : "badge-progress"}`}>
                      {r.status}
                    </span>
                  </td>
                  <td>{r.yamls?.length ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
