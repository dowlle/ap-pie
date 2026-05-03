import CopyButton from "./CopyButton";

/**
 * Hero treatment for the connection host:port string.
 *
 * Used on /r/<id> when the room has an external server registered, and on
 * /play/<seed> when there's a connection URL to surface. Earns top-of-page
 * real estate because once a multiworld is generated, this string is the
 * single most useful piece of information on the page.
 */
export type ConnectionStatus = "live" | "warn" | "error" | "pending" | "external";

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  live: "Live",
  warn: "Server stopped",
  error: "Server crashed",
  pending: "Starting up",
  external: "Hosted externally",
};

export default function ConnectionHero({
  url,
  status,
  meta,
}: {
  url: string;
  status: ConnectionStatus;
  meta?: string;
}) {
  // 'external' is informational rather than a real liveness - paint it as
  // the warm accent dot so it reads as "we point here, host owns uptime."
  const dotClass =
    status === "live" ? "conn-hero-dot--live" :
    status === "warn" ? "conn-hero-dot--warn" :
    status === "error" ? "conn-hero-dot--error" :
    status === "pending" ? "conn-hero-dot--pending" :
    "conn-hero-dot--pending"; // external uses the same warm dot

  return (
    <section className="conn-hero" aria-label="Connection details">
      <span className="conn-hero-status">
        <span className={`conn-hero-dot ${dotClass}`} aria-hidden="true" />
        {STATUS_LABELS[status]}
      </span>
      <code className="conn-hero-url">{url}</code>
      <CopyButton value={url} label="Copy address" copiedLabel="Copied" />
      {meta && <p className="conn-hero-meta">{meta}</p>}
    </section>
  );
}
