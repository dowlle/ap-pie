import { useNavigate } from "react-router-dom";
import type { GameRecord } from "../api";

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatusBadge({ record }: { record: GameRecord }) {
  if (!record.has_save) return null;
  if (record.all_goals_completed) return <span className="badge badge-done">DONE</span>;
  if (record.overall_completion_pct > 0) return <span className="badge badge-progress">IN PROGRESS</span>;
  return <span className="badge badge-save">SAVE</span>;
}

function CompletionBar({ pct }: { pct: number }) {
  return (
    <div className="completion-bar">
      <div className="completion-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
      <span className="completion-text">{pct.toFixed(0)}%</span>
    </div>
  );
}

interface Props {
  games: GameRecord[];
}

export default function GameTable({ games }: Props) {
  const navigate = useNavigate();

  if (games.length === 0) {
    return <p className="empty">No matching games found.</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="game-table">
        <thead>
          <tr>
            <th>Seed</th>
            <th>Version</th>
            <th>Created</th>
            <th>Players</th>
            <th>Games</th>
            <th>Completion</th>
            <th>Last Played</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {games.map((g) => (
            <tr
              key={g.seed}
              onClick={() => navigate(`/games/${g.seed}`)}
              className="clickable"
            >
              <td className="seed">{g.seed}</td>
              <td>{g.ap_version}</td>
              <td>{formatDate(g.creation_time)}</td>
              <td>{g.player_count}</td>
              <td className="games-cell">{g.games.join(", ")}</td>
              <td>
                {g.has_save ? <CompletionBar pct={g.overall_completion_pct} /> : "-"}
              </td>
              <td>{formatDate(g.last_activity)}</td>
              <td><StatusBadge record={g} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
