import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getTrackers, registerTracker, type TrackerInfo } from "../api";

export default function MarketLanding() {
  const [url, setUrl] = useState("");
  const [trackers, setTrackers] = useState<TrackerInfo[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getTrackers().then(setTrackers).catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setError("");
    setLoading(true);
    try {
      const result = await registerTracker(url.trim());
      navigate(`/market/${result.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to tracker");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Market</h1>
      <p className="page-desc">
        Enter an Archipelago tracker URL to view or create item trade listings for that game.
      </p>

      <form onSubmit={handleSubmit} className="tracker-form">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://archipelago.gg/tracker/..."
          className="tracker-url-input"
          required
        />
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Connecting..." : "Connect"}
        </button>
      </form>
      {error && <p className="upload-error">{error}</p>}

      {trackers.length > 0 && (
        <>
          <h2>Recent Tracked Games</h2>
          <div className="table-wrapper">
            <table className="game-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Host</th>
                  <th>Last Synced</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {trackers.map((t) => (
                  <tr key={t.id}>
                    <td>{t.display_name || t.id}</td>
                    <td>{t.host}</td>
                    <td>{t.last_synced ? new Date(t.last_synced).toLocaleString() : "Never"}</td>
                    <td>
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => navigate(`/market/${t.id}`)}
                      >
                        Open Market
                      </button>
                    </td>
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
