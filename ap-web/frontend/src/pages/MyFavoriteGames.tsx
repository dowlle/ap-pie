import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAPWorlds, type APWorldInfo } from "../api";
import FavoriteGameButton from "../components/FavoriteGameButton";
import { useFavoriteGames } from "../lib/useFavoriteGames";

export default function MyFavoriteGames() {
  const favorites = useFavoriteGames();
  const [worlds, setWorlds] = useState<APWorldInfo[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    getAPWorlds().then((items) => { if (!cancelled) setWorlds(items); })
      .catch(() => { if (!cancelled) setError("Game details could not be loaded. Your saved favorites are still available."); });
    return () => { cancelled = true; };
  }, []);
  return <section className="settings-section">
    <h2>My favorite games</h2>
    <p>Keep the games you want to play together here. <Link to="/apworlds">Browse games</Link> to add more.</p>
    {(favorites.error || error) && <p role="alert" className="error">{favorites.error || error}</p>}
    {favorites.loading ? <p>Loading favorites...</p> : favorites.games.length === 0 ?
      <p>No favorite games yet. Choose “Save favorite” on a game in the catalog.</p> :
      <div className="favorite-games-grid">{favorites.games.map((name) => {
        const world = worlds.find((item) => item.name === name);
        const version = world?.downloadable_versions[0]?.version;
        return <article className="favorite-game-card" key={name}>
          <h3>{world?.display_name || name}</h3>
          <div className="favorite-game-actions">
            {version && !world?.disabled && <Link className="btn btn-primary btn-sm"
              to={`/yaml-builder/${encodeURIComponent(name)}?version=${encodeURIComponent(version)}`}>Create YAML</Link>}
            <Link className="btn btn-sm" to={`/apworlds?search=${encodeURIComponent(name)}`}>View game</Link>
            <FavoriteGameButton name={world?.display_name || name} saved disabled={favorites.pending !== null}
              onClick={() => void favorites.toggle(name)} />
          </div>
        </article>;
      })}</div>}
  </section>;
}
