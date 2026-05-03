import { useEffect, useState } from "react";
import { getAPWorlds, type APWorldInfo } from "../api";

/**
 * Module-level promise cache for `/api/apworlds`. The index is large
 * (~450 entries) but rarely changes, and several pages (RoomDetail,
 * RoomPublic, anywhere a YAML game cell renders) want a `game_name ->
 * APWorldInfo` lookup at the same time. Cache once per page load.
 *
 * Failure clears the cache so a later mount can retry.
 */
let cache: Promise<Map<string, APWorldInfo>> | null = null;

function loadLookup(): Promise<Map<string, APWorldInfo>> {
  if (!cache) {
    cache = getAPWorlds()
      .then(
        (worlds) =>
          new Map(
            worlds
              .filter((w) => w.game_name)
              .map((w) => [w.game_name, w]),
          ),
      )
      .catch((e) => {
        cache = null;
        throw e;
      });
  }
  return cache;
}

/**
 * Returns the `game_name -> APWorldInfo` lookup once it loads. Renders
 * pass `null` until the fetch completes; callers should treat a null
 * lookup as "not in index" (links degrade to plain text). The hook does
 * not surface load errors - the worst case is unlinked game names,
 * which is the correct fallback.
 */
export function useAPWorldLookup(): Map<string, APWorldInfo> | null {
  const [lookup, setLookup] = useState<Map<string, APWorldInfo> | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadLookup()
      .then((m) => {
        if (!cancelled) setLookup(m);
      })
      .catch(() => {
        // Swallow: callers degrade to plain text on null.
      });
    return () => {
      cancelled = true;
    };
  }, []);
  return lookup;
}
