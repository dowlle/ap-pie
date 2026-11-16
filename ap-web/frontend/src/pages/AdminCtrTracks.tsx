import { useEffect, useState } from "react";
import {
  adminCtrApproveBatch,
  adminCtrEditTrack,
  adminCtrSubmissionAction,
  adminCtrSubmissions,
  adminCtrTrackAction,
  adminCtrTracks,
  type CtrAdminSubmission,
  type CtrAdminTrack,
} from "../api";
import { usePageTitle } from "../lib/usePageTitle";

/**
 * Review queue for the CTR custom-track name registry. Three lists:
 * pending submissions (approve, reject, merge into a track), candidate tracks
 * (the Saphi import, approved in batches) and the tracks Stef has approved
 * (edit title and credits, promote to a named block, withdraw).
 */
export default function AdminCtrTracks() {
  usePageTitle("CTR track registry");
  const [subs, setSubs] = useState<CtrAdminSubmission[]>([]);
  const [tracks, setTracks] = useState<CtrAdminTrack[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [version, setVersion] = useState(0);
  const refresh = async () => { setVersion((v) => v + 1); };
  useEffect(() => {
    let live = true;
    Promise.all([adminCtrSubmissions("pending"), adminCtrTracks()])
      .then(([s, t]) => {
        if (!live) return;
        setSubs(s);
        setTracks(t);
        setSelected(new Set());
      })
      .catch((e) => { if (live) setError(e instanceof Error ? e.message : "Failed to load"); });
    return () => { live = false; };
  }, [version]);

  const run = async (fn: () => Promise<unknown>, done = "") => {
    setError(""); setNotice("");
    try { await fn(); if (done) setNotice(done); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
  };

  const candidates = tracks.filter((t) => t.state === "candidate");
  const reviewed = tracks.filter((t) => t.state !== "candidate");
  const toggle = (id: number) => setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <>
      <h1>CTR track registry</h1>
      {error && <p style={{ color: "var(--accent-warn)" }}>{error}</p>}
      {notice && <p>{notice}</p>}

      <h2>Submissions waiting ({subs.length})</h2>
      {subs.length === 0 && <p className="muted">Nothing waiting.</p>}
      {subs.map((s) => (
        <div key={s.id} className="card" style={{ margin: "0.5rem 0", padding: "0.75rem" }}>
          <strong>{s.title ?? s.target_title ?? "Submission"}</strong>{" "}
          <span className="muted">
            {s.kind.replace("_", " ")} from {s.source === "saphi_import" ? "the Saphi import" : s.submitter_name ?? "a deleted account"}
          </span>
          {typeof s.payload?.note === "string" && s.payload.note && <p>{s.payload.note}</p>}
          <div>
            <button className="btn btn-sm" onClick={() => run(() => adminCtrSubmissionAction(s.id, "approve"), "Approved.")}>Approve</button>{" "}
            <button className="btn btn-sm" onClick={() => {
              const raw = prompt("Merge into which track id? (see the list below)");
              const id = raw ? Number(raw) : NaN;
              if (Number.isInteger(id)) run(() => adminCtrSubmissionAction(s.id, "merge", { entry_id: id }), "Merged.");
            }}>Merge</button>{" "}
            <button className="btn btn-sm" onClick={() => {
              const reason = prompt("Reason (the submitter sees it):", "");
              if (reason !== null) run(() => adminCtrSubmissionAction(s.id, "reject", { reason }), "Rejected.");
            }}>Reject</button>
          </div>
        </div>
      ))}

      <h2>Candidates ({candidates.length})</h2>
      <p className="muted">Imported from Project Saphi. Tick the ones to approve in one batch.</p>
      {candidates.length > 0 && (
        <p>
          <button className="btn btn-sm" disabled={selected.size === 0}
            onClick={() => run(async () => {
              const r = await adminCtrApproveBatch([...selected]);
              setNotice(`Approved ${r.approved.length}${r.failed.length ? `, ${r.failed.length} failed` : ""}.`);
            })}>Approve {selected.size} selected</button>{" "}
          <button className="btn btn-sm" onClick={() => setSelected(new Set(candidates.map((c) => c.id)))}>Select all</button>
        </p>
      )}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {candidates.map((c) => (
          <li key={c.id}>
            <label>
              <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} /> #{c.id} {c.display_title}
              <span className="muted"> {c.credits.map((x) => x.name).join(", ")} ({c.revisions.length} versions)</span>
            </label>
          </li>
        ))}
      </ul>

      <h2>Reviewed tracks ({reviewed.length})</h2>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {reviewed.map((t) => (
          <li key={t.id} style={{ margin: "0.4rem 0" }}>
            #{t.id} <strong>{t.display_title}</strong>{" "}
            <span className="muted">
              {t.track_key} | {t.state}
              {t.block_index !== null && ` | block ${t.block_index}: ${t.ap_name}${t.shipped_in ? ` (shipped in ${t.shipped_in})` : ""}`}
              {t.report_count > 0 && ` | ${t.report_count} reports`}
            </span>{" "}
            <button className="btn btn-sm" onClick={() => {
              const title = prompt("Display title:", t.display_title);
              if (title) run(() => adminCtrEditTrack(t.id, { display_title: title }), "Saved.");
            }}>Edit title</button>{" "}
            {t.state === "approved" && (
              <button className="btn btn-sm" onClick={() => {
                if (confirm("Promote assigns a permanent block. Continue?")) run(() => adminCtrTrackAction(t.id, "promote"), "Promoted.");
              }}>Promote</button>
            )}{" "}
            {t.state === "withdrawn" || t.state === "source-unavailable" ? (
              <button className="btn btn-sm" onClick={() => run(() => adminCtrTrackAction(t.id, "restore"))}>Restore</button>
            ) : (
              <button className="btn btn-sm" onClick={() => run(() => adminCtrTrackAction(t.id, "withdraw"))}>Withdraw</button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
