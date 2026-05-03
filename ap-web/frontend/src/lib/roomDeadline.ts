/** FEAT-04 helpers: submit_deadline lives in the API as an ISO 8601 UTC string,
 *  but the host UI wants a `<input type="datetime-local">` (no TZ in the value)
 *  and the public lobby wants a friendly local-time + countdown display.
 *
 *  The browser's `<input type="datetime-local">` value is `YYYY-MM-DDTHH:MM`
 *  in the user's local timezone with no offset. Round-tripping correctly
 *  means parsing it as local, then converting to UTC ISO before sending. The
 *  server returns ISO with TZ, which we convert back to a local
 *  `datetime-local` value when putting it back in the input.
 */

const pad = (n: number) => n.toString().padStart(2, "0");

/** Convert an ISO timestamp (any TZ) into a `datetime-local` input value
 *  using the user's local timezone. Returns "" for null/empty. */
export function isoToLocalInputValue(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Convert a `datetime-local` input value (interpreted as local time) into
 *  a UTC ISO 8601 string suitable for the API. Returns null for "". */
export function localInputValueToIso(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** Format a deadline as an absolute local-time string for display
 *  (e.g. "Sat, May 15, 2026, 14:30 CEST"). */
export function formatDeadlineAbsolute(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

/** Format the gap to a deadline as a short countdown ("in 2h 15m", "in 3d",
 *  "5 minutes ago"). Returns "" when no deadline is set. */
export function formatDeadlineCountdown(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "";
  const target = new Date(iso).getTime();
  if (isNaN(target)) return "";
  const diffMs = target - now;
  const past = diffMs < 0;
  const abs = Math.abs(diffMs);
  const sec = Math.floor(abs / 1000);
  const min = Math.floor(sec / 60);
  const hr = Math.floor(min / 60);
  const day = Math.floor(hr / 24);

  let core: string;
  if (day >= 2) core = `${day} days`;
  else if (hr >= 2) core = `${hr} hours`;
  else if (hr === 1) core = `1h ${min - 60}m`;
  else if (min >= 2) core = `${min} minutes`;
  else if (min === 1) core = "1 minute";
  else core = `${sec} seconds`;

  return past ? `${core} ago` : `in ${core}`;
}
