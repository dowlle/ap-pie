import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getTrackerInfo,
  getTrackerListings,
  getTrackerMatches,
  createTrackerListing,
  updateTrackerListing,
  deleteTrackerListing,
  type TrackerDetail,
  type MarketListing,
  type MarketMatch,
} from "../api";
import ItemAutocomplete from "../components/ItemAutocomplete";

interface TrackerPlayer {
  slot: number;
  name: string;
  game: string;
  checks_done?: number;
  checks_total?: number;
}

function CreateListingForm({
  trackerId,
  players,
  onCreated,
}: {
  trackerId: string;
  players: TrackerPlayer[];
  onCreated: () => void;
}) {
  const [slot, setSlot] = useState(players[0]?.slot ?? 1);
  const [itemName, setItemName] = useState("");
  const [type, setType] = useState<"offer" | "request">("offer");
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  const selectedPlayer = players.find((p) => p.slot === slot);
  const game = selectedPlayer?.game ?? "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemName.trim()) return;
    setError("");
    try {
      await createTrackerListing(trackerId, {
        slot,
        player_name: selectedPlayer?.name ?? `Player ${slot}`,
        item_name: itemName.trim(),
        listing_type: type,
        quantity,
      });
      setItemName("");
      setQuantity(1);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="market-form">
      <select value={slot} onChange={(e) => setSlot(Number(e.target.value))}>
        {players.map((p) => (
          <option key={p.slot} value={p.slot}>
            P{p.slot}: {p.name} ({p.game})
          </option>
        ))}
      </select>
      <select value={type} onChange={(e) => setType(e.target.value as "offer" | "request")}>
        <option value="offer">Offering</option>
        <option value="request">Looking for</option>
      </select>
      <ItemAutocomplete game={game} value={itemName} onChange={setItemName} />
      <input
        type="number"
        min={1}
        value={quantity}
        onChange={(e) => setQuantity(Number(e.target.value))}
        className="qty-input"
      />
      <button type="submit" className="btn btn-primary">Post</button>
      {error && <span className="upload-error">{error}</span>}
    </form>
  );
}

function ListingRow({
  listing,
  trackerId,
  matchedIds,
  onUpdate,
}: {
  listing: MarketListing;
  trackerId: string;
  matchedIds: Set<number>;
  onUpdate: () => void;
}) {
  const isMatch = matchedIds.has(listing.id);

  const handleFulfill = async () => {
    await updateTrackerListing(trackerId, listing.id, { status: "fulfilled" });
    onUpdate();
  };

  const handleCancel = async () => {
    await updateTrackerListing(trackerId, listing.id, { status: "cancelled" });
    onUpdate();
  };

  const handleDelete = async () => {
    await deleteTrackerListing(trackerId, listing.id);
    onUpdate();
  };

  return (
    <tr className={isMatch ? "row-match" : ""}>
      <td>
        <span className={`badge ${listing.listing_type === "offer" ? "badge-done" : "badge-progress"}`}>
          {listing.listing_type}
        </span>
      </td>
      <td>{listing.item_name}</td>
      <td>{listing.quantity}</td>
      <td>{listing.player_name}</td>
      <td>
        {isMatch && <span className="badge badge-done">Match found!</span>}
      </td>
      <td>
        <div className="listing-actions">
          {listing.status === "active" && (
            <>
              <button className="btn btn-sm" onClick={handleFulfill}>Fulfill</button>
              <button className="btn btn-sm" onClick={handleCancel}>Cancel</button>
            </>
          )}
          <button className="btn btn-sm btn-danger" onClick={handleDelete}>Delete</button>
        </div>
      </td>
    </tr>
  );
}

export default function MarketTracker() {
  const { trackerId } = useParams<{ trackerId: string }>();
  const [tracker, setTracker] = useState<TrackerDetail | null>(null);
  const [listings, setListings] = useState<MarketListing[]>([]);
  const [completedListings, setCompletedListings] = useState<MarketListing[]>([]);
  const [matches, setMatches] = useState<MarketMatch[]>([]);
  const [tab, setTab] = useState<"all" | "offers" | "requests">("all");
  const [showCompleted, setShowCompleted] = useState(false);
  const [error, setError] = useState("");

  const refresh = () => {
    if (!trackerId) return;
    getTrackerListings(trackerId).then(setListings);
    getTrackerListings(trackerId, "fulfilled").then((fulfilled) => {
      getTrackerListings(trackerId, "cancelled").then((cancelled) => {
        setCompletedListings([...fulfilled, ...cancelled]);
      });
    });
    getTrackerMatches(trackerId).then(setMatches);
  };

  useEffect(() => {
    if (!trackerId) return;
    getTrackerInfo(trackerId)
      .then(setTracker)
      .catch(() => setError("Failed to load tracker"));
    refresh();
  }, [trackerId]);

  if (!trackerId) return null;
  if (error) return <p className="upload-error">{error}</p>;
  if (!tracker) return <p className="loading">Loading...</p>;

  const players: TrackerPlayer[] = tracker.tracker_data?.players ?? [];
  const games: string[] = tracker.tracker_data?.games ?? [];

  const matchedIds = new Set<number>();
  for (const m of matches) {
    matchedIds.add(m.offer_id);
    matchedIds.add(m.request_id);
  }

  const filtered =
    tab === "all"
      ? listings
      : listings.filter((l) =>
          tab === "offers" ? l.listing_type === "offer" : l.listing_type === "request"
        );

  return (
    <div>
      <Link to="/market" className="back-link">&larr; Back to Market</Link>

      <h1>Market - {tracker.display_name || tracker.id}</h1>

      {players.length > 0 && (
        <div className="tracker-players">
          <h3>Players ({players.length})</h3>
          <div className="player-grid">
            {players.map((p) => (
              <div key={p.slot} className="player-card">
                <strong>P{p.slot}: {p.name}</strong>
                <span className="player-game">{p.game}</span>
                {p.checks_total ? (
                  <span className="player-checks">
                    {p.checks_done}/{p.checks_total} checks
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}

      {games.length > 0 && (
        <p className="game-tags">
          Games: {games.map((g) => (
            <span key={g} className="badge">{g}</span>
          ))}
        </p>
      )}

      {matches.length > 0 && (
        <div className="match-banner">
          {matches.length} match{matches.length !== 1 ? "es" : ""} found!
        </div>
      )}

      {players.length > 0 && (
        <CreateListingForm trackerId={trackerId} players={players} onCreated={refresh} />
      )}

      <div className="market-tabs">
        <button
          className={`btn btn-sm ${tab === "all" ? "btn-primary" : ""}`}
          onClick={() => setTab("all")}
        >
          All ({listings.length})
        </button>
        <button
          className={`btn btn-sm ${tab === "offers" ? "btn-primary" : ""}`}
          onClick={() => setTab("offers")}
        >
          Offers ({listings.filter((l) => l.listing_type === "offer").length})
        </button>
        <button
          className={`btn btn-sm ${tab === "requests" ? "btn-primary" : ""}`}
          onClick={() => setTab("requests")}
        >
          Requests ({listings.filter((l) => l.listing_type === "request").length})
        </button>
      </div>

      {filtered.length === 0 ? (
        <p className="empty">No active listings yet. Be the first to post!</p>
      ) : (
        <div className="table-wrapper">
          <table className="game-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Item</th>
                <th>Qty</th>
                <th>Player</th>
                <th>Match</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((l) => (
                <ListingRow
                  key={l.id}
                  listing={l}
                  trackerId={trackerId}
                  matchedIds={matchedIds}
                  onUpdate={refresh}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {completedListings.length > 0 && (
        <div className="completed-section">
          <button
            className="btn btn-sm"
            onClick={() => setShowCompleted(!showCompleted)}
          >
            {showCompleted ? "Hide" : "Show"} Completed/Cancelled ({completedListings.length})
          </button>
          {showCompleted && (
            <div className="table-wrapper">
              <table className="game-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Item</th>
                    <th>Qty</th>
                    <th>Player</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {completedListings.map((l) => (
                    <tr key={l.id} className="row-completed">
                      <td>
                        <span className={`badge ${l.listing_type === "offer" ? "badge-done" : "badge-progress"}`}>
                          {l.listing_type}
                        </span>
                      </td>
                      <td>{l.item_name}</td>
                      <td>{l.quantity}</td>
                      <td>{l.player_name}</td>
                      <td>
                        <span className={`badge ${l.status === "fulfilled" ? "badge-done" : "badge-inactive"}`}>
                          {l.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
