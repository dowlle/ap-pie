import { useEffect, useState, useRef } from "react";
import { getRoomItemTracker, type ItemTrackerData, type PlayerItems, type ReceivedItem } from "../api";

const CLASS_COLORS: Record<string, string> = {
  progression: "var(--green)",
  useful: "var(--blue)",
  trap: "#f87171",
  filler: "var(--text-muted)",
};

const CLASS_ORDER = ["progression", "useful", "trap", "filler"] as const;

function ItemRow({ item }: { item: ReceivedItem }) {
  return (
    <div className="item-row">
      <span className="item-dot" style={{ background: CLASS_COLORS[item.classification] }} />
      <span className="item-name">{item.item_name}</span>
      <span className="item-sender">
        {item.location_name !== "Starting item"
          ? `from ${item.sender_name} @ ${item.location_name}`
          : "starting item"}
      </span>
    </div>
  );
}

function CountsBadge({ counts }: { counts: PlayerItems["item_counts"] }) {
  return (
    <div className="item-summary-bar">
      {CLASS_ORDER.map((cls) => (
        counts[cls] > 0 && (
          <span key={cls} className="item-count-badge" style={{ color: CLASS_COLORS[cls] }}>
            {counts[cls]} {cls}
          </span>
        )
      ))}
    </div>
  );
}

function PlayerItemList({ player }: { player: PlayerItems }) {
  const [search, setSearch] = useState("");
  const [showFiller, setShowFiller] = useState(false);

  const filtered = player.received_items.filter((it) => {
    if (search && !it.item_name.toLowerCase().includes(search.toLowerCase())) return false;
    if (!showFiller && it.classification === "filler" && !search) return false;
    return true;
  });

  const grouped: Record<string, ReceivedItem[]> = {};
  for (const cls of CLASS_ORDER) {
    const items = filtered.filter((it) => it.classification === cls);
    if (items.length > 0) grouped[cls] = items;
  }

  return (
    <div className="item-player-list">
      <CountsBadge counts={player.item_counts} />
      <div className="item-controls">
        <input
          className="item-search"
          placeholder="Search items..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {!search && (
          <label className="item-toggle">
            <input type="checkbox" checked={showFiller} onChange={(e) => setShowFiller(e.target.checked)} />
            Show filler ({player.item_counts.filler})
          </label>
        )}
      </div>
      {Object.entries(grouped).map(([cls, items]) => (
        <div key={cls} className="item-group">
          <div className="item-group-header" style={{ color: CLASS_COLORS[cls] }}>
            {cls} ({items.length})
          </div>
          {items.map((it, i) => (
            <ItemRow key={`${it.item_id}-${i}`} item={it} />
          ))}
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="muted">No items {search ? "matching search" : "received yet"}</p>
      )}
    </div>
  );
}

export default function ItemTracker({ roomId }: { roomId: string }) {
  const [data, setData] = useState<ItemTrackerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSlot, setActiveSlot] = useState<number | null>(null);
  const intervalRef = useRef<number | null>(null);

  const fetchData = () => {
    getRoomItemTracker(roomId)
      .then((d) => {
        setData(d);
        setLoading(false);
        if (d.players.length > 0 && activeSlot === null) {
          setActiveSlot(d.players[0].slot);
        }
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
    intervalRef.current = window.setInterval(fetchData, 20000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [roomId]);

  if (loading) return <p className="loading">Loading item data...</p>;
  if (!data || data.status !== "ok") return <p className="muted">No item data available yet.</p>;

  const activePlayer = data.players.find((p) => p.slot === activeSlot) ?? data.players[0];

  return (
    <div className="item-tracker">
      {!data.has_datapackage && (
        <p className="muted" style={{ marginBottom: "0.5rem" }}>
          Item names unavailable - start the server to resolve them.
        </p>
      )}

      {data.players.length > 1 && (
        <div className="market-tabs">
          {data.players.map((p) => (
            <button
              key={p.slot}
              className={`btn btn-sm${activeSlot === p.slot ? " btn-primary" : ""}`}
              onClick={() => setActiveSlot(p.slot)}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}

      {activePlayer && (
        <>
          <div className="item-player-header">
            <span className="item-player-name">{activePlayer.name}</span>
            <span className="item-player-game">{activePlayer.game}</span>
            <span className="muted">{activePlayer.received_items.length} items received</span>
          </div>
          <PlayerItemList player={activePlayer} />
        </>
      )}
    </div>
  );
}
