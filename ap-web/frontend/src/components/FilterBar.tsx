import { type GameFilters } from "../api";

interface Props {
  filters: GameFilters;
  onChange: (filters: GameFilters) => void;
}

export default function FilterBar({ filters, onChange }: Props) {
  const set = (key: keyof GameFilters, value: string) => {
    onChange({ ...filters, [key]: value || undefined });
  };

  return (
    <div className="filter-bar">
      <input
        type="text"
        placeholder="Filter by game..."
        value={filters.game ?? ""}
        onChange={(e) => set("game", e.target.value)}
      />
      <input
        type="text"
        placeholder="Filter by player..."
        value={filters.player ?? ""}
        onChange={(e) => set("player", e.target.value)}
      />
      <input
        type="text"
        placeholder="Filter by seed..."
        value={filters.seed ?? ""}
        onChange={(e) => set("seed", e.target.value)}
      />
      <input
        type="text"
        placeholder="Version (e.g. 0.6.7)"
        value={filters.version ?? ""}
        onChange={(e) => set("version", e.target.value)}
      />
      <select
        value={filters.has_save ?? ""}
        onChange={(e) => set("has_save", e.target.value)}
      >
        <option value="">All games</option>
        <option value="true">With save</option>
        <option value="false">Without save</option>
      </select>
      <select
        value={filters.sort ?? "date"}
        onChange={(e) => set("sort", e.target.value)}
      >
        <option value="date">Sort by date</option>
        <option value="seed">Sort by seed</option>
        <option value="players">Sort by players</option>
        <option value="completion">Sort by completion</option>
        <option value="last_played">Sort by last played</option>
      </select>
    </div>
  );
}
