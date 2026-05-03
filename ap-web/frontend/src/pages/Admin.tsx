import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAdminUsers, setUserApproval, type AuthUser } from "../api";

export default function Admin() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdminUsers()
      .then(setUsers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const toggleApproval = async (user: AuthUser) => {
    try {
      const updated = await setUserApproval(user.id, !user.is_approved);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) return <p>Loading...</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <div>
      <h2>User Management</h2>
      <table className="game-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Discord ID</th>
            <th>Admin</th>
            <th>Approved</th>
            <th>Joined</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.discord_username}</td>
              <td style={{ fontFamily: "monospace", fontSize: "0.85rem" }}>{u.discord_id}</td>
              <td>{u.is_admin ? "Yes" : "No"}</td>
              <td>{u.is_approved ? "Yes" : "No"}</td>
              <td>{new Date(u.created_at).toLocaleDateString()}</td>
              <td>
                <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", alignItems: "center" }}>
                  <button
                    className={`btn btn-sm ${u.is_approved ? "btn-danger" : "btn-primary"}`}
                    onClick={() => toggleApproval(u)}
                    disabled={u.is_admin}
                    title={u.is_admin ? "Admins are always approved" : ""}
                  >
                    {u.is_approved ? "Revoke" : "Approve"}
                  </button>
                  <Link
                    to={`/rooms?as_user=${u.id}`}
                    className="btn btn-sm"
                    title={`View rooms hosted by ${u.discord_username}`}
                  >
                    View rooms
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
