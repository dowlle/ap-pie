import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getGame, getServerStatus, launchServer, stopServer, sendServerCommand, type GameRecord, type ServerInstance } from "../api";
import ShareGame from "../components/ShareGame";
import { copyText } from "../lib/copy";

function InlineCopy({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-sm"
      onClick={async () => {
        const ok = await copyText(value);
        if (ok) {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }
      }}
    >
      {copied ? "Copied!" : label}
    </button>
  );
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

function CompletionBar({ pct }: { pct: number }) {
  return (
    <div className="completion-bar completion-bar-lg">
      <div className="completion-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
      <span className="completion-text">{pct.toFixed(1)}%</span>
    </div>
  );
}

function statusClass(status: number): string {
  if (status >= 30) return "badge-done";
  if (status >= 20) return "badge-progress";
  if (status >= 5) return "badge-save";
  return "";
}

function downloadLog(seed: string, lines: string[]) {
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `server-${seed}.log`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function ServerLog({ seed, log }: { seed: string; log: string[] }) {
  if (!log.length) return null;
  return (
    <details className="gen-log-details">
      <summary className="gen-log-summary">
        Server Log
        <button className="btn btn-sm" style={{ marginLeft: "0.75rem" }} onClick={(e) => { e.preventDefault(); downloadLog(seed, log); }}>
          Download
        </button>
      </summary>
      <pre className="gen-log">{log.join("\n")}</pre>
    </details>
  );
}

function CommandInput({ seed, onSent }: { seed: string; onSent: () => void }) {
  const [cmd, setCmd] = useState("");
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = cmd.trim();
    if (!trimmed) return;
    setSending(true);
    try {
      await sendServerCommand(seed, trimmed);
      setCmd("");
      setTimeout(onSent, 500);
    } catch {
      // ignore - server might have stopped
    } finally {
      setSending(false);
    }
  };

  return (
    <form className="server-command" onSubmit={handleSubmit}>
      <input
        type="text"
        className="server-command-input"
        value={cmd}
        onChange={(e) => setCmd(e.target.value)}
        placeholder="Type a server command..."
        disabled={sending}
      />
      <button className="btn btn-sm" type="submit" disabled={sending || !cmd.trim()}>
        Send
      </button>
    </form>
  );
}

function ServerPanel({ seed }: { seed: string }) {
  const [server, setServer] = useState<ServerInstance | null>(null);
  const [action, setAction] = useState<"idle" | "starting" | "stopping" | "confirm">("idle");
  const [error, setError] = useState("");

  const refresh = () => {
    getServerStatus(seed).then(setServer).catch(() => setServer(null));
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [seed]);

  const handleLaunch = async () => {
    setAction("starting");
    setError("");
    try {
      const s = await launchServer(seed);
      setServer(s);
      setAction("idle");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
      setAction("idle");
    }
  };

  const handleStop = async () => {
    setAction("stopping");
    try {
      await stopServer(seed);
      refresh();
    } finally {
      setAction("idle");
    }
  };

  const isRunning = server?.status === "running";

  return (
    <div className="server-panel">
      <h3>Server</h3>
      {error && <p className="error">{error}</p>}

      {isRunning ? (
        <>
          <div className="server-panel-running">
            <div className="server-info">
              <span className="server-label">Status</span>
              <span className="badge badge-done">Running</span>
            </div>
            <div className="server-info">
              <span className="server-label">Connect</span>
              <code className="connection-url">{server.connection_url}</code>
              <InlineCopy value={server.connection_url} />
            </div>
            <div className="server-info">
              <span className="server-label">Port</span>
              <span>{server.port}</span>
            </div>
            <ShareGame seed={seed} buttonLabel="Share" buttonClassName="btn btn-primary" />
            <button className="btn btn-danger" onClick={handleStop} disabled={action === "stopping"}>
              {action === "stopping" ? "Stopping..." : "Stop Server"}
            </button>
          </div>
          <CommandInput seed={seed} onSent={refresh} />
          {server?.recent_log && <ServerLog seed={seed} log={server.recent_log} />}
        </>
      ) : (
        <div>
          {server && server.status !== "running" && (
            <p className="muted">Server is {server.status}</p>
          )}
          {server?.recent_log && <ServerLog seed={seed} log={server.recent_log} />}
          {action === "confirm" ? (
            <div className="launch-confirm">
              <span>Launch server for this game?</span>
              <button className="btn btn-primary" onClick={handleLaunch}>
                Yes, start
              </button>
              <button className="btn" onClick={() => setAction("idle")}>Cancel</button>
            </div>
          ) : (
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                className="btn btn-primary"
                onClick={() => setAction("confirm")}
              >
                Launch Server
              </button>
              <ShareGame seed={seed} buttonLabel="Share" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function GameDetail() {
  const { seed } = useParams<{ seed: string }>();
  const [game, setGame] = useState<GameRecord | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!seed) return;
    getGame(seed).then(setGame).catch(() => setError("Game not found"));
  }, [seed]);

  if (error) return <p className="error">{error}</p>;
  if (!game) return <p className="loading">Loading...</p>;

  return (
    <div>
      <Link to="/" className="back-link">&larr; Back to games</Link>

      <div className="detail-header">
        <div className="page-header">
          <h1>Seed {game.seed}</h1>
          <Link to={`/games/${game.seed}/market`} className="btn">Market</Link>
        </div>
        <div className="detail-meta">
          <span>AP {game.ap_version}</span>
          <span>Created {formatDate(game.creation_time)}</span>
          {game.last_activity && <span>Last played {formatDate(game.last_activity)}</span>}
        </div>
      </div>

      <ServerPanel seed={game.seed} />

      {game.has_save && (
        <div className="detail-completion">
          <h3>Overall Completion</h3>
          <CompletionBar pct={game.overall_completion_pct} />
          {game.all_goals_completed && <span className="badge badge-done">ALL GOALS COMPLETE</span>}
        </div>
      )}

      <h2>Players ({game.player_count})</h2>
      <div className="table-wrapper">
        <table className="game-table">
          <thead>
            <tr>
              <th>Slot</th>
              <th>Player</th>
              <th>Game</th>
              <th>World Version</th>
              <th>Checks</th>
              <th>Completion</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {game.players.map((p) => (
              <tr key={p.slot}>
                <td>P{p.slot}</td>
                <td>{p.name}</td>
                <td>{p.game}</td>
                <td className="muted">{game.game_versions?.[p.game] ? `v${game.game_versions[p.game]}` : "-"}</td>
                <td>{p.checks_total > 0 ? `${p.checks_done}/${p.checks_total}` : "-"}</td>
                <td>
                  {p.checks_total > 0 ? <CompletionBar pct={p.completion_pct} /> : "-"}
                </td>
                <td>
                  {p.client_status > 0 && (
                    <span className={`badge ${statusClass(p.client_status)}`}>
                      {p.status_label}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="detail-section">
        <h3>Server Options</h3>
        <dl className="detail-grid">
          <dt>Race Mode</dt><dd>{game.race_mode}</dd>
          <dt>Hint Cost</dt><dd>{game.hint_cost ?? "-"}</dd>
          <dt>Release</dt><dd>{game.release_mode ?? "-"}</dd>
          <dt>Collect</dt><dd>{game.collect_mode ?? "-"}</dd>
          <dt>Spoiler</dt><dd>{game.spoiler ? "Yes" : "No"}</dd>
        </dl>
      </div>

      {game.patch_files.length > 0 && (
        <div className="detail-section">
          <h3>Patch Files</h3>
          <ul>
            {game.patch_files.map((f) => <li key={f}>{f}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
