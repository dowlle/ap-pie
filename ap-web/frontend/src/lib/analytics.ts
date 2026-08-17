/**
 * FEAT-31: the browser half of the cookieless analytics log.
 *
 * Only sends what the server structurally cannot see: which SPA view is on
 * screen (the backend catch-all serves the same index.html for every client
 * route) and how far someone gets inside the YAML builder before leaving.
 * Everything else is recorded server-side.
 *
 * The privacy rules this file has to hold up:
 *
 * - **Nothing is written to the device.** No cookie, no localStorage, no
 *   sessionStorage. `visitId` below is a random value in this module's
 *   memory; a reload creates a new one and the old one is unrecoverable, so
 *   it cannot link two visits, two tabs, or two devices. It exists purely so
 *   a single visit's steps can be counted as one visit.
 * - **Opt-out is honoured client-side too.** If the browser exposes Global
 *   Privacy Control or Do Not Track, this module sends nothing at all. The
 *   server independently strips identifiers from any request carrying those
 *   headers, so the two layers fail safe in both directions.
 * - **No content, ever.** Only the fields declared per event below: game
 *   names, versions, and short enum-shaped strings. Never YAML, never a
 *   player name, never a room name, never free text.
 *
 * Delivery is best-effort by design: `keepalive` fetch, failures swallowed,
 * and an unload event sent via sendBeacon. If a blocker eats the request,
 * nothing about the site changes.
 */

type ClientEventKind =
  | "page_view"
  | "builder_opened"
  | "builder_yaml_emitted"
  | "builder_abandoned"
  | "apworld_download_clicked";

type EventProps = Record<string, string | number | boolean | undefined>;

interface QueuedEvent {
  kind: ClientEventKind;
  visit_id?: string;
  room_id?: string;
  props?: EventProps;
}

const ENDPOINT = "/api/events";

/**
 * Per-page-load id, memory only. Deliberately NOT persisted anywhere: see
 * the module comment. Hex from crypto when available so it is not a
 * predictable counter, with a plain-random fallback for old browsers.
 */
const visitId: string = (() => {
  try {
    const buf = new Uint8Array(8);
    crypto.getRandomValues(buf);
    return Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return Math.random().toString(16).slice(2, 18).padEnd(16, "0");
  }
})();

/** True when the visitor has signalled an objection to analytics. */
function optedOut(): boolean {
  try {
    const nav = navigator as Navigator & { globalPrivacyControl?: boolean; doNotTrack?: string };
    if (nav.globalPrivacyControl === true) return true;
    const dnt = nav.doNotTrack ?? (window as unknown as { doNotTrack?: string }).doNotTrack;
    return dnt === "1" || dnt === "yes";
  } catch {
    return false;
  }
}

const disabled = optedOut();

function send(event: QueuedEvent): void {
  if (disabled) return;
  const body = JSON.stringify({ ...event, visit_id: visitId });
  try {
    void fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      credentials: "same-origin",
      keepalive: true,
    }).catch(() => {
      /* analytics must never surface an error to the user */
    });
  } catch {
    /* ignore */
  }
}

/** Fire-and-forget variant for unload paths, where fetch may be cancelled. */
function sendBeacon(event: QueuedEvent): void {
  if (disabled) return;
  const body = JSON.stringify({ ...event, visit_id: visitId });
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
      return;
    }
  } catch {
    /* fall through */
  }
  send(event);
}

/**
 * Which SPA view the visitor is looking at. Takes a coarse view NAME rather
 * than the URL: room ids and query strings stay out of the log, and the
 * server records only the request path (always "/api/events" here).
 */
export function trackPageView(view: string, roomId?: string): void {
  send({ kind: "page_view", room_id: roomId, props: { view } });
}

export function trackBuilderOpened(game: string, version: string, surface: string, roomId?: string): void {
  send({ kind: "builder_opened", room_id: roomId, props: { game, version, surface } });
}

/** action: download | submit | add_to_room | create_room */
export function trackBuilderEmitted(
  game: string,
  version: string,
  action: string,
  roomId?: string,
): void {
  send({ kind: "builder_yaml_emitted", room_id: roomId, props: { game, version, action } });
}

/** stage: the furthest step reached before the builder was closed. */
export function trackBuilderAbandoned(game: string, version: string, stage: string, roomId?: string): void {
  sendBeacon({ kind: "builder_abandoned", room_id: roomId, props: { game, version, stage } });
}

export function trackApworldDownloadClicked(name: string, version: string, surface: string): void {
  send({ kind: "apworld_download_clicked", props: { name, version, surface } });
}

/** Exposed for tests and for the privacy page's claims to stay checkable. */
export const analyticsDisabled = disabled;
