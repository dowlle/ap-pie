import type { FuzzResult } from "../api";

/**
 * FEAT-35: per-version fuzz verdict pill.
 *
 * Renders the empirical fuzz verdict from `dowlle/Archipelago-index` so
 * hosts and players can see at a glance whether a given (apworld, version)
 * generates cleanly. Four states:
 *
 *   - null     -> render nothing (no fuzz data yet)
 *   - "clean"  -> tiny green dot
 *   - "flaky"  -> tiny amber dot
 *   - "broken" -> tiny red dot
 *
 * All variants share the dot shape; only colour changes. The tooltip
 * carries the detail (verdict + default-hook rate + worst-hook rate +
 * seeds + fuzzed_at). Decision (2026-05-13): keep the visual footprint
 * tiny so it never competes with the version pill or aux icons -- hover
 * surfaces the breakdown for hosts who want it.
 *
 * Locked design decisions (2026-05-13):
 *   - per-version pills everywhere (no overall card badge)
 *   - warn-only (no hide, no expander, no toggle)
 *   - silent absence (no "unknown" fallback)
 *
 * `*_rate` fields in `FuzzResult` are decimals (0.004 = 0.4%); the
 * tooltip multiplies by 100 for display with two-decimal precision so a
 * 0.4% vs 0.6% flaky distinction is readable.
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

  return (
    <span
      className={`fuzz-pill fuzz-pill-${fuzz_result.verdict}`}
      title={tooltip}
      aria-label={tooltip}
    >
      <span className="fuzz-pill-dot" aria-hidden="true" />
    </span>
  );
}
