import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  deletePreset,
  getMyPresets,
  updatePreset,
  type Preset,
} from "../api";
import { usePageTitle } from "../lib/usePageTitle";

/**
 * FEAT-42: the author's own preset library.
 *
 * This is the second half of the save-then-publish model. "Save as preset"
 * in the builder writes a private draft with no ceremony; this page is where
 * a draft gets a description and becomes public, which keeps the deliberate
 * part deliberate without an approval queue standing between anyone and
 * publishing.
 *
 * It is also the FEAT-23 surface (personal YAML templates): a private preset
 * that is never published is exactly the "save my own setup and reuse it"
 * feature that row asked for.
 */
export default function MyPresets({ embedded = false }: { embedded?: boolean } = {}) {
  // Rendered standalone at /presets (legacy path) and inside the FEAT-43
  // hub, which supplies its own heading.
  usePageTitle(embedded ? null : "My presets");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [drafts, setDrafts] = useState<Record<number, { name: string; description: string }>>({});

  const load = () => {
    setLoading(true);
    getMyPresets()
      .then((list) => {
        setPresets(list);
        setDrafts(
          Object.fromEntries(
            list.map((p) => [p.id, { name: p.name, description: p.description }]),
          ),
        );
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load presets"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const patch = async (p: Preset, body: Parameters<typeof updatePreset>[1]) => {
    setBusyId(p.id);
    setError("");
    try {
      const updated = await updatePreset(p.id, body);
      setPresets((prev) => prev.map((x) => (x.id === p.id ? updated : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update preset");
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (p: Preset) => {
    setBusyId(p.id);
    try {
      await deletePreset(p.id);
      setPresets((prev) => prev.filter((x) => x.id !== p.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete preset");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div>
      {!embedded && <h1>My presets</h1>}
      <p className="muted" style={{ marginBottom: "1.25rem" }}>
        Configurations you saved from the YAML builder. They stay private until
        you publish them. Published presets appear for everyone building a YAML
        for that game, with your Discord name attached.
      </p>

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="loading">Loading...</p>
      ) : presets.length === 0 ? (
        <p className="muted">
          Nothing saved yet. Build a YAML on the{" "}
          <Link to="/apworlds">APWorlds page</Link> and use "Save as preset" on
          the review step.
        </p>
      ) : (
        <ul className="preset-manage-list">
          {presets.map((p) => {
            const draft = drafts[p.id] ?? { name: p.name, description: p.description };
            const dirty = draft.name !== p.name || draft.description !== p.description;
            const publishable = draft.description.trim().length > 0;
            return (
              <li key={p.id} className="preset-manage-row settings-section">
                <div className="preset-manage-head">
                  <span className="preset-manage-game">
                    {p.apworld_name} <span className="muted">v{p.version}</span>
                  </span>
                  <span className="preset-manage-badges">
                    {p.is_official && <span className="badge badge-builtin">official</span>}
                    {p.kind === "advanced" && <span className="badge badge-save">advanced</span>}
                    <span className={`badge ${p.status === "published" ? "badge-done" : ""}`}>
                      {p.status === "published" ? "published" : p.status}
                    </span>
                  </span>
                </div>

                <label className="preset-manage-field">
                  <span>Name</span>
                  <input
                    type="text"
                    value={draft.name}
                    maxLength={80}
                    onChange={(e) =>
                      setDrafts((d) => ({ ...d, [p.id]: { ...draft, name: e.target.value } }))
                    }
                  />
                </label>
                <label className="preset-manage-field">
                  <span>Description</span>
                  <textarea
                    value={draft.description}
                    maxLength={500}
                    rows={2}
                    placeholder="What is this preset for? Required before publishing."
                    onChange={(e) =>
                      setDrafts((d) => ({
                        ...d,
                        [p.id]: { ...draft, description: e.target.value },
                      }))
                    }
                  />
                </label>

                <p className="preset-manage-meta muted">
                  {p.uses === 1 ? "used once" : `used ${p.uses} times`}
                  {p.score > 0 && ` · ${p.score} upvote${p.score === 1 ? "" : "s"}`}
                  {p.kind === "simple" && p.values &&
                    ` · ${Object.keys(p.values).length} option${
                      Object.keys(p.values).length === 1 ? "" : "s"
                    }`}
                </p>

                <div className="preset-manage-actions">
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={!dirty || busyId === p.id}
                    onClick={() => patch(p, { name: draft.name, description: draft.description })}
                  >
                    Save changes
                  </button>
                  {p.status === "published" ? (
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={busyId === p.id}
                      onClick={() => patch(p, { status: "private" })}
                    >
                      Unpublish
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-sm btn-primary"
                      disabled={busyId === p.id || !publishable}
                      title={
                        publishable
                          ? "Make this preset available to everyone building a YAML for this game"
                          : "Add a description first, so people know what this preset is for"
                      }
                      onClick={async () => {
                        if (dirty) {
                          await patch(p, { name: draft.name, description: draft.description });
                        }
                        await patch(p, { status: "published" });
                      }}
                    >
                      Publish
                    </button>
                  )}
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busyId === p.id}
                    onClick={() => remove(p)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
