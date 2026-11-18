import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import {
  getCtrTracks,
  getMyCtrSubmissions,
  reportCtrTrack,
  submitCtrTrack,
  type CtrCredit,
  type CtrSubmission,
  type CtrTrack,
} from "../api";
import { useAuth } from "../context/AuthContext";
import { useFeature } from "../context/FeaturesContext";
import { usePageTitle } from "../lib/usePageTitle";

/**
 * CTR custom-track name registry, player side: browse the reviewed names and
 * propose a new track, a new revision, or a correction. Nothing a player
 * submits is public until it is reviewed. Beta only while the ctr_registry
 * feature flag is off in production.
 */
export default function CtrTracks() {
  usePageTitle("CTR custom tracks");
  const enabled = useFeature("ctr_registry");
  const { user, login } = useAuth();
  const [tracks, setTracks] = useState<CtrTrack[]>([]);
  const [mine, setMine] = useState<CtrSubmission[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadTracks = () => getCtrTracks(q).then(setTracks).catch((e) => setError(String(e.message ?? e)));
  const loadMine = () => { if (user) getMyCtrSubmissions().then(setMine).catch(() => {}); };

  useEffect(() => { if (enabled) loadTracks(); }, [enabled, q]);
  useEffect(() => { if (enabled) loadMine(); }, [enabled, user]);

  if (!enabled) return <Navigate to="/" replace />;

  return (
    <>
      <h1>CTR custom tracks</h1>
      <p className="muted" style={{ maxWidth: "60rem" }}>
        Reviewed titles and credits for CTR Archipelago custom tracks. This registry holds names,
        credits, hashes and links only; downloads stay on the creators' pages.
        Submissions are reviewed before anything shows here.
      </p>
      {error && <p style={{ color: "var(--accent-warn)" }}>{error}</p>}
      {notice && <p>{notice}</p>}

      <div className="filter-bar" style={{ marginTop: "1rem" }}>
        <input placeholder="Search title or creator" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {tracks.length === 0 && <p className="muted">No reviewed tracks yet.</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {tracks.map((t) => (
          <TrackRow key={t.track_key} track={t} signedIn={!!user} onNotice={setNotice} />
        ))}
      </ul>

      <h2>Propose a track</h2>
      {user ? (
        <ProposeForm onDone={() => { setNotice("Submitted. It shows here after review."); loadMine(); }} />
      ) : (
        <p><button className="btn" onClick={() => login("/custom-tracks")}>Sign in with Discord to submit</button></p>
      )}

      {user && mine.length > 0 && (
        <>
          <h2>Your submissions</h2>
          <ul>
            {mine.map((s) => (
              <li key={s.id}>
                {s.title ?? s.target_track_key ?? "Submission"} ({s.kind.replace("_", " ")}): {s.status}
                {s.reject_reason ? `, ${s.reject_reason}` : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function TrackRow({ track, signedIn, onNotice }: { track: CtrTrack; signedIn: boolean; onNotice: (m: string) => void }) {
  const report = async () => {
    const reason = prompt("What is wrong with this entry?") ?? "";
    try {
      const r = await reportCtrTrack(track.track_key, reason);
      onNotice(r.status === "reported" ? "Thanks, reported." : "You already reported this one.");
    } catch (e) {
      onNotice(e instanceof Error ? e.message : "Could not report");
    }
  };
  return (
    <li style={{ margin: "0.5rem 0" }}>
      <strong>{track.display_title}</strong>
      {track.credits.length > 0 && <span className="muted"> by {track.credits.map((c) => c.name).join(", ")}</span>}
      {track.ap_name && <span className="muted"> | named block: {track.ap_name}</span>}
      {" "}
      {Object.entries(track.links).map(([kind, url]) => (
        <a key={kind} href={url} target="_blank" rel="noreferrer noopener" style={{ marginRight: "0.5rem" }}>{kind}</a>
      ))}
      {signedIn && <button className="btn btn-sm" onClick={report}>Report</button>}
    </li>
  );
}

function ProposeForm({ onDone }: { onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [creator, setCreator] = useState("");
  const [saphi, setSaphi] = useState("");
  const [descriptor, setDescriptor] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setErr("");
    let parsed: unknown;
    if (descriptor.trim()) {
      try { parsed = JSON.parse(descriptor); } catch { setErr("The descriptor is not valid JSON."); return; }
    }
    const credits: CtrCredit[] = creator.trim() ? [{ name: creator.trim(), role: "track" }] : [];
    setBusy(true);
    try {
      await submitCtrTrack({
        kind: "new_track", title, credits,
        links: saphi.trim() ? { saphi: saphi.trim() } : {},
        descriptor: parsed, note,
      });
      setTitle(""); setCreator(""); setSaphi(""); setDescriptor(""); setNote("");
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not submit");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} style={{ display: "grid", gap: "0.5rem", maxWidth: "36rem" }}>
      <label>Title (40 characters at most)
        <input value={title} maxLength={40} required onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>Creator
        <input value={creator} maxLength={48} onChange={(e) => setCreator(e.target.value)} />
      </label>
      <label>Project Saphi page (optional, https link)
        <input value={saphi} maxLength={300} onChange={(e) => setSaphi(e.target.value)} />
      </label>
      <label>Descriptor exported by the in-game manager (optional JSON)
        <textarea rows={5} value={descriptor} onChange={(e) => setDescriptor(e.target.value)} />
      </label>
      <label>Note for the reviewer (optional)
        <input value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} />
      </label>
      {err && <p style={{ color: "var(--accent-warn)" }}>{err}</p>}
      <div><button className="btn" type="submit" disabled={busy}>{busy ? "Sending..." : "Submit for review"}</button></div>
    </form>
  );
}
