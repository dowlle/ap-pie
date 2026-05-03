import { useEffect, useState } from "react";
import { getSummary, type Summary as SummaryType } from "../api";

export default function Summary() {
  const [data, setData] = useState<SummaryType | null>(null);

  useEffect(() => {
    getSummary().then(setData);
  }, []);

  if (!data) return <p className="loading">Loading...</p>;

  return (
    <div>
      <h1>Summary</h1>

      <div className="summary-stats">
        <div className="stat-card">
          <div className="stat-value">{data.total_games}</div>
          <div className="stat-label">Total Games</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.games_with_save}</div>
          <div className="stat-label">With Save</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.games_by_frequency.length}</div>
          <div className="stat-label">Unique Games</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data.players_by_frequency.length}</div>
          <div className="stat-label">Unique Players</div>
        </div>
      </div>

      <div className="summary-columns">
        <div>
          <h2>Games by Frequency</h2>
          <table className="game-table">
            <thead><tr><th>Game</th><th>Count</th></tr></thead>
            <tbody>
              {data.games_by_frequency.map(([name, count]) => (
                <tr key={name}><td>{name}</td><td>{count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h2>Players by Frequency</h2>
          <table className="game-table">
            <thead><tr><th>Player</th><th>Count</th></tr></thead>
            <tbody>
              {data.players_by_frequency.slice(0, 25).map(([name, count]) => (
                <tr key={name}><td>{name}</td><td>{count}</td></tr>
              ))}
            </tbody>
          </table>
          {data.players_by_frequency.length > 25 && (
            <p className="muted">...and {data.players_by_frequency.length - 25} more</p>
          )}
        </div>

        <div>
          <h2>AP Versions</h2>
          <table className="game-table">
            <thead><tr><th>Version</th><th>Count</th></tr></thead>
            <tbody>
              {data.versions.map(([ver, count]) => (
                <tr key={ver}><td>{ver}</td><td>{count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
