import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getServers, stopServer, type ServerInstance } from "../api";

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function StatusDot({ status }: { status: string }) {
  const cls =
    status === "running" ? "dot-running" :
    status === "crashed" ? "dot-crashed" : "dot-stopped";
  return <span className={`status-dot ${cls}`} />;
}

export default function Servers() {
  const [servers, setServers] = useState<ServerInstance[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = () => {
    getServers().then(setServers).finally(() => setLoading(false));
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStop = async (seed: string) => {
    await stopServer(seed);
    refresh();
  };

  if (loading) return <p className="loading">Loading...</p>;

  const running = servers.filter((s) => s.status === "running");
  const stopped = servers.filter((s) => s.status !== "running");

  return (
    <div>
      <h1>Running Servers</h1>

      {running.length === 0 ? (
        <p className="empty">No servers are currently running.</p>
      ) : (
        <div className="server-grid">
          {running.map((s) => (
            <div key={s.seed} className="server-card">
              <div className="server-card-header">
                <StatusDot status={s.status} />
                <Link to={`/games/${s.seed}`} className="server-seed">{s.seed}</Link>
              </div>
              <div className="server-card-body">
                <div className="server-info">
                  <span className="server-label">Connect</span>
                  <code className="connection-url">{s.connection_url}</code>
                </div>
                <div className="server-info">
                  <span className="server-label">Port</span>
                  <span>{s.port}</span>
                </div>
                <div className="server-info">
                  <span className="server-label">Uptime</span>
                  <span>{formatUptime(s.uptime_seconds)}</span>
                </div>
                <div className="server-info">
                  <span className="server-label">Players</span>
                  <span>{s.players.join(", ")}</span>
                </div>
              </div>
              <div className="server-card-footer">
                <button className="btn btn-danger" onClick={() => handleStop(s.seed)}>
                  Stop
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {stopped.length > 0 && (
        <>
          <h2>Stopped / Crashed</h2>
          <div className="table-wrapper">
            <table className="game-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Seed</th>
                  <th>Port</th>
                  <th>Started</th>
                </tr>
              </thead>
              <tbody>
                {stopped.map((s) => (
                  <tr key={s.seed}>
                    <td><StatusDot status={s.status} /> {s.status}</td>
                    <td><Link to={`/games/${s.seed}`}>{s.seed}</Link></td>
                    <td>{s.port}</td>
                    <td>{new Date(s.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
