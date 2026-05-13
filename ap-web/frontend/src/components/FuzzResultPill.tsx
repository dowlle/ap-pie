import type { FuzzResult } from "../api";

/**
 * FEAT-35: per-version fuzz verdict pill.
 *
 * Renders the empirical fuzz verdict from `dowlle/Archipelago-index` so
 * hosts and players can see at a glance whether a given (apworld, version)
 * generates cleanly. Three states:
 *
 *   - null               -> render nothing (no fuzz data yet)
 *   - "clean"            -> tiny green dot, no text (least intrusive)
 *   - "flaky" | "broken" -> coloured pill "<verdict> N%" with a tooltip
 *                          carrying worst_hook + rate + fuzzed_at + seeds
 *
 * Locked design decisions (2026-05-13):
 *   - per-version pills everywhere (no overall card badge)
 *   - warn-only (no hide, no expander, no toggle)
 *   - silent absence (no "unknown" fallback)
 *
 * `*_rate` fields in `FuzzResult` are decimals (0.004 = 0.4%); the
 * component multiplies by 100 for display. The tooltip shows two-decimal
 * precision for `default` and `worst_hook` rates so a 0.4% vs 0.6% flaky
 * distinction is readable.
 */
export default function FuzzResultPill({
  fuzz_result,
  version,
}: {
  fuzz_result: FuzzResult | null;
  /** Optional version string, used to prefix the tooltip for clarity when
   *  the pill renders far from the version it describes. */
  version?: string;
}) {
  if (!fuzz_result) return null;
  const prefix = version ? `v${version}: ` : "";
  const defaultPct = (fuzz_result.default_rate * 100).toFixed(2);
  const worstPct = (fuzz_result.worst_hook_rate * 100).toFixed(2);
  const tooltip =
    `${prefix}${fuzz_result.verdict} ` +
    `(default ${defaultPct}%, worst ${fuzz_result.worst_hook} ${worstPct}%) ` +
    `· ${fuzz_result.seeds} seeds · fuzzed ${fuzz_result.fuzzed_at}`;

  if (fuzz_result.verdict === "clean") {
    return (
      <span
        className="fuzz-pill fuzz-pill-clean"
        title={tooltip}
        aria-label={tooltip}
      >
        <span className="fuzz-pill-dot" aria-hidden="true" />
      </span>
    );
  }

  const cls =
    fuzz_result.verdict === "broken"
      ? "fuzz-pill fuzz-pill-broken"
      : "fuzz-pill fuzz-pill-flaky";
  // Render `<verdict> N%` where N is the default-hook failure rate. The
  // tooltip carries the worst-hook breakdown for hosts who want detail.
  const label = `${fuzz_result.verdict} ${defaultPct}%`;
  return (
    <span className={cls} title={tooltip} aria-label={tooltip}>
      {label}
    </span>
  );
}
