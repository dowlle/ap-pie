import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteRoomTemplate,
  listRoomTemplates,
  updateRoomTemplate,
  type RoomTemplate,
} from "../api";

/**
 * FEAT-33: management page for the current user's room creation templates.
 *
 * Lists every template the user owns. Each row supports inline rename, a
 * default-toggle (radio across the rows so picking one unsets others), and
 * a delete button. New templates are created from CreateRoomModal's "Save
 * as template" button — there is no creation surface here on purpose, since
 * templates are most usefully captured in-context with the modal already
 * filled in.
 */
export default function MyRoomTemplates() {
  const [templates, setTemplates] = useState<RoomTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [renameDraft, setRenameDraft] = useState<Record<number, string>>({});

  useEffect(() => {
    listRoomTemplates()
      .then(({ templates }) => {
        setTemplates(templates);
        setRenameDraft(Object.fromEntries(templates.map(t => [t.id, t.name])));
      })
      .catch(err => {
        setLoadError(err instanceof Error ? err.message : "Failed to load templates.");
      })
      .finally(() => setLoading(false));
  }, []);

  const refresh = () => {
    listRoomTemplates()
      .then(({ templates }) => {
        setTemplates(templates);
        setRenameDraft(Object.fromEntries(templates.map(t => [t.id, t.name])));
      })
      .catch(err => setActionError(err instanceof Error ? err.message : "Refresh failed."));
  };

  const handleRename = async (id: number) => {
    setActionError("");
    const draft = (renameDraft[id] ?? "").trim();
    const current = templates.find(t => t.id === id);
    if (!current) return;
    if (!draft) {
      setActionError("Template name can't be empty.");
      setRenameDraft(d => ({ ...d, [id]: current.name }));
      return;
    }
    if (draft === current.name) return;
    try {
      const updated = await updateRoomTemplate(id, { name: draft });
      setTemplates(ts => ts.map(t => t.id === id ? updated : t));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Rename failed.");
      setRenameDraft(d => ({ ...d, [id]: current.name }));
    }
  };

  const handleSetDefault = async (id: number) => {
    setActionError("");
    try {
      await updateRoomTemplate(id, { is_default: true });
      // Refresh: the API only returns the updated row, but other rows had
      // their is_default cleared as part of the same transaction.
      refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't set default.");
    }
  };

  const handleClearDefault = async (id: number) => {
    setActionError("");
    try {
      const updated = await updateRoomTemplate(id, { is_default: false });
      setTemplates(ts => ts.map(t => t.id === id ? updated : t));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Couldn't clear default.");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!window.confirm(`Delete template "${name}"? This cannot be undone.`)) return;
    setActionError("");
    try {
      await deleteRoomTemplate(id);
      setTemplates(ts => ts.filter(t => t.id !== id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Delete failed.");
    }
  };

  if (loading) return <p className="muted">Loading templates...</p>;
  if (loadError) return <p className="settings-error">{loadError}</p>;

  return (
    <div className="my-templates">
      <header className="my-templates-header">
        <h1>My room templates</h1>
        <p className="muted">
          Save and reuse room settings across your rooms. Capture a new template
          from the "Save as template" button in any room creation. The default
          template, if you set one, auto-applies whenever you open the create-
          room dialog.
        </p>
      </header>

      {actionError && <p className="settings-error">{actionError}</p>}

      {templates.length === 0 ? (
        <p className="muted">
          You don't have any templates yet. Open <Link to="/rooms">Rooms</Link>,
          start creating a room, set the fields the way you like, and click
          "Save as template" in the footer.
        </p>
      ) : (
        <table className="my-templates-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Default</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {templates.map(t => (
              <tr key={t.id}>
                <td>
                  <input
                    type="text"
                    value={renameDraft[t.id] ?? t.name}
                    maxLength={80}
                    onChange={(e) => setRenameDraft(d => ({ ...d, [t.id]: e.target.value }))}
                    onBlur={() => handleRename(t.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                      if (e.key === "Escape") {
                        setRenameDraft(d => ({ ...d, [t.id]: t.name }));
                        (e.target as HTMLInputElement).blur();
                      }
                    }}
                    className="my-templates-name"
                  />
                </td>
                <td>
                  {t.is_default ? (
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => handleClearDefault(t.id)}
                      title="Stop auto-applying this template on modal open."
                    >
                      Default ✓ (clear)
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => handleSetDefault(t.id)}
                      title="Auto-apply this template whenever you open the Create room modal."
                    >
                      Set as default
                    </button>
                  )}
                </td>
                <td className="muted">{t.updated_at.slice(0, 10)}</td>
                <td>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => handleDelete(t.id, t.name)}
                    title="Delete this template permanently."
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
