import { useEffect, useRef, useState } from "react";
import { getFavoriteGames, setFavoriteGame } from "../api";
import { useAuth } from "../context/AuthContext";

export function useFavoriteGames() {
  const { user } = useAuth();
  const owner = user?.id;
  const [state, setState] = useState<{ owner: number | undefined; games: string[] }>({ owner: undefined, games: [] });
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const currentOwner = useRef(owner);
  useEffect(() => {
    currentOwner.current = owner;
    let cancelled = false;
    if (owner === undefined) return;
    getFavoriteGames().then((games) => {
      if (!cancelled) { setState({ owner, games }); setError(""); }
    }).catch((reason) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load favorites");
    });
    return () => { cancelled = true; };
  }, [owner]);
  const games = state.owner === owner ? state.games : [];
  const toggle = async (name: string) => {
    if (owner === undefined || busy.current) return;
    busy.current = true;
    setPending(name);
    setError("");
    try {
      const updated = await setFavoriteGame(name, !games.includes(name));
      if (currentOwner.current === owner) setState({ owner, games: updated });
    } catch (reason) {
      if (currentOwner.current === owner) setError(reason instanceof Error ? reason.message : "Could not save favorite");
    } finally { busy.current = false; setPending(null); }
  };
  return { games, loading: owner !== undefined && state.owner !== owner && !error, pending, error, toggle };
}
