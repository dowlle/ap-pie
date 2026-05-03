import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getMarketListings,
  getMarketMatches,
  createListing,
  updateListing,
  deleteListing,
  getGame,
  type MarketListing,
  type MarketMatch,
  type GameRecord,
} from "../api";

function CreateListingForm({ seed, game, onCreated }: { seed: string; game: GameRecord; onCreated: () => void }) {
  const [slot, setSlot] = useState(game.players[0]?.slot ?? 1);
  const [itemName, setItemName] = useState("");
  const [type, setType] = useState<"offer" | "request">("offer");
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemName.trim()) return;
    setError("");
    try {
      const player = game.players.find((p) => p.slot === slot);
      await createListing(seed, {
        slot,
        player_name: player?.name ?? `Player ${slot}`,
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
        {game.players.map((p) => (
          <option key={p.slot} value={p.slot}>P{p.slot}: {p.name} ({p.game})</option>
        ))}
      </select>
      <select value={type} onChange={(e) => setType(e.target.value as "offer" | "request")}>
        <option value="offer">Offering</option>
        <option value="request">Looking for</option>
      </select>
      <input
        type="text"
        placeholder="Item name..."
        value={itemName}
        onChange={(e) => setItemName(e.target.value)}
        required
      />
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

function ListingRow({ listing, seed, matchedIds, onUpdate }: {
  listing: MarketListing;
  seed: string;
  matchedIds: Set<number>;
  onUpdate: () => void;
}) {
  const isMatch = matchedIds.has(listing.id);

  const handleFulfill = async () => {
    await updateListing(seed, listing.id, { status: "fulfilled" });
    onUpdate();
  };

  const handleDelete = async () => {
    await deleteListing(seed, listing.id);
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
        {isMatch && <span className="badge badge-done">Match!</span>}
      </td>
      <td>
        <div className="listing-actions">
          <button className="btn btn-sm" onClick={handleFulfill}>Fulfill</button>
          <button className="btn btn-sm btn-danger" onClick={handleDelete}>Delete</button>
        </div>
      </td>
    </tr>
  );
}

export default function Market() {
  const { seed } = useParams<{ seed: string }>();
  const [game, setGame] = useState<GameRecord | null>(null);
  const [listings, setListings] = useState<MarketListing[]>([]);
  const [matches, setMatches] = useState<MarketMatch[]>([]);
  const [tab, setTab] = useState<"all" | "offers" | "requests">("all");

  const refresh = () => {
    if (!seed) return;
    getMarketListings(seed).then(setListings);
    getMarketMatches(seed).then(setMatches);
  };

  useEffect(() => {
    if (!seed) return;
    getGame(seed).then(setGame);
    refresh();
  }, [seed]);

  if (!seed) return null;
  if (!game) return <p className="loading">Loading...</p>;

  const matchedIds = new Set<number>();
  for (const m of matches) {
    matchedIds.add(m.offer_id);
    matchedIds.add(m.request_id);
  }

  const filtered = tab === "all" ? listings :
    listings.filter((l) => tab === "offers" ? l.listing_type === "offer" : l.listing_type === "request");

  return (
    <div>
      <Link to={`/games/${seed}`} className="back-link">&larr; Back to game</Link>

      <h1>Market - Seed {seed}</h1>

      {matches.length > 0 && (
        <div className="match-banner">
          {matches.length} match{matches.length !== 1 ? "es" : ""} found!
        </div>
      )}

      <CreateListingForm seed={seed} game={game} onCreated={refresh} />

      <div className="market-tabs">
        <button className={`btn btn-sm ${tab === "all" ? "btn-primary" : ""}`} onClick={() => setTab("all")}>
          All ({listings.length})
        </button>
        <button className={`btn btn-sm ${tab === "offers" ? "btn-primary" : ""}`} onClick={() => setTab("offers")}>
          Offers ({listings.filter((l) => l.listing_type === "offer").length})
        </button>
        <button className={`btn btn-sm ${tab === "requests" ? "btn-primary" : ""}`} onClick={() => setTab("requests")}>
          Requests ({listings.filter((l) => l.listing_type === "request").length})
        </button>
      </div>

      {filtered.length === 0 ? (
        <p className="empty">No listings yet. Be the first to post!</p>
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
                <ListingRow key={l.id} listing={l} seed={seed} matchedIds={matchedIds} onUpdate={refresh} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
