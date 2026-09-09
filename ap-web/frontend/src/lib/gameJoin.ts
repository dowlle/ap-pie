/** Verified client integrations only. Never derive a destination from a game label.
 * PokepelagoClient GameContext reads host, port and name and auto-connects.
 */
const WEB_CLIENTS: Record<string, string> = {
  Pokepelago: "https://pokepelago.ap-pie.com/",
  "Poképelago": "https://pokepelago.ap-pie.com/",
};

export function gameJoinUrl(game: string, slotName: string, connection: string): string | null {
  const destination = Object.hasOwn(WEB_CLIENTS, game) ? WEB_CLIENTS[game] : null;
  if (!destination || !slotName || !connection) return null;
  // The tracker supplies host:port, including bare or bracketed IPv6 hosts.
  const match = connection.match(/^(\[[^\]]+\]|[^\s/?#@]+):(\d+)$/);
  if (!match) return null;
  const port = Number(match[2]);
  if (!Number.isInteger(port) || port < 1 || port > 65535) return null;
  const host = match[1].includes(":") && !match[1].startsWith("[") ? `[${match[1]}]` : match[1];
  try {
    const address = new URL(`http://${host}:${port}`);
    if (!address.hostname || address.username || address.password || address.pathname !== "/") return null;
    const url = new URL(destination);
    url.searchParams.set("host", address.hostname);
    url.searchParams.set("port", String(port));
    url.searchParams.set("name", slotName);
    return url.href;
  } catch {
    return null;
  }
}
