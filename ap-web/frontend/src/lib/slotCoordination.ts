/** Small shared helpers for the tracker cards and slot modal. */
export function bkDuration(since: string, now = Date.now()): string {
  const elapsed = Math.max(0, now - new Date(since).getTime());
  if (!Number.isFinite(elapsed) || elapsed < 60_000) return "<1m";
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h`;
  return `${Math.floor(minutes / 1440)}d`;
}

export function matchesCoordination(
  state: { bk_since: string | null; go_mode_since: string | null } | undefined,
  onlyBK: boolean, onlyGoMode: boolean,
): boolean {
  return (!onlyBK || !!state?.bk_since) && (!onlyGoMode || !!state?.go_mode_since);
}
