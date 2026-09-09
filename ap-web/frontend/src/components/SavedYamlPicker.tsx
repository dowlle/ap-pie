import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getMyYamls, type UserYaml } from "../api";
import { useAuth } from "../context/AuthContext";

export default function SavedYamlPicker({ roomId, host = false }: { roomId: string; host?: boolean }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState<UserYaml[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!user || !open) return;
    getMyYamls().then(setItems).catch(() => setError("Could not load your YAMLs. Close and reopen this chooser to retry."));
  }, [user, open]);
  if (!user) return <p><a href={`/api/auth/login?next=${encodeURIComponent(`/r/${roomId}`)}`}>Sign in to use a saved YAML</a></p>;
  return <section className="settings-section">
    <button className="btn" type="button" onClick={() => setOpen(!open)}>{open ? "Close saved YAMLs" : "Use a saved YAML"}</button>
    {open && <>
      <p>Your original stays in My YAMLs. Review this room's version and validation before submitting.</p>
      <select aria-label="Saved YAML to use" value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">Choose a saved setup…</option>
        {items.map(item => <option key={item.id} value={item.id}>{item.label || item.apworld_name} · v{item.version}</option>)}
      </select>
      <button className="btn btn-primary" type="button" disabled={!selected} onClick={() => {
        const item = items.find(row => String(row.id) === selected);
        if (item) navigate(`/yaml-builder/${encodeURIComponent(item.apworld_name)}?context=${host ? "host-room" : "public-room"}&room=${encodeURIComponent(roomId)}&from=${item.id}`);
      }}>Review for this room</button>
      {error && <p role="alert">{error}</p>}
      {!items.length && !error && <p>No saved setups loaded. <Link to="/my/yamls">Open My YAMLs</Link>.</p>}
    </>}
  </section>;
}
