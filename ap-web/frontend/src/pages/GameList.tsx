import { useEffect, useState, useRef, useCallback } from "react";
import { getGames, type GameRecord, type GameFilters } from "../api";
import FilterBar from "../components/FilterBar";
import GameTable from "../components/GameTable";
import UploadButton from "../components/UploadButton";

export default function GameList() {
  const [games, setGames] = useState<GameRecord[]>([]);
  const [filters, setFilters] = useState<GameFilters>({ sort: "date" });
  const [loading, setLoading] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const fetchGames = useCallback(() => {
    setLoading(true);
    getGames(filters)
      .then(setGames)
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchGames, 200);
    return () => clearTimeout(debounceRef.current);
  }, [fetchGames]);

  return (
    <div>
      <div className="page-header">
        <h1>Generated Games</h1>
        <UploadButton onUploaded={fetchGames} />
      </div>
      <FilterBar filters={filters} onChange={setFilters} />
      {loading ? (
        <p className="loading">Loading...</p>
      ) : (
        <>
          <p className="result-count">{games.length} game(s)</p>
          <GameTable games={games} />
        </>
      )}
    </div>
  );
}
