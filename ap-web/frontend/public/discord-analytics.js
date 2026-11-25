export function isDiscordInvite(url) {
  if (url.protocol !== "https:" && url.protocol !== "http:") return false;
  if (url.hostname === "discord.gg") return url.pathname.length > 1;
  return url.hostname === "discord.com" && /^\/invite\/[^/]+\/?$/.test(url.pathname);
}

function recordDiscordClick(event) {
  if (event.button !== (event.type === "auxclick" ? 1 : 0)) return;
  const link = event.target instanceof Element && event.target.closest("a[href]");
  if (!link || !isDiscordInvite(new URL(link.href, document.baseURI))) return;

  // Keep the request alive during navigation without sending the invite URL,
  // referrer, session cookie or any browser-generated visit identifier.
  void fetch("/api/events", {
    method: "POST",
    credentials: "omit",
    referrerPolicy: "no-referrer",
    keepalive: true,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind: "discord_invite_click" }),
  }).catch(() => {});
}

if (typeof document !== "undefined") {
  document.addEventListener("click", recordDiscordClick);
  document.addEventListener("auxclick", recordDiscordClick);
}
