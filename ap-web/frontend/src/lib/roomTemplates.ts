/**
 * FEAT-33: per-user room creation templates.
 *
 * Helpers shared between CreateRoomModal (apply + save-as) and the
 * /me/room-templates management page (list + rename + delete + set-default).
 *
 * Smart deadline encoding: the template stores the *intent* (a time-of-day
 * + day-offset, both editable) and the modal stores the *artifact* (an
 * absolute datetime in the host's local timezone via <input type="datetime-
 * local">). applyTemplateToModal computes the artifact from the intent at
 * apply-time; captureTemplateFromModal round-trips the artifact back to an
 * intent at save-time relative to today.
 */

export type ApworldPolicy = "strict" | "flexible" | "latest";

export interface RoomTemplatePayload {
  description: string;
  require_discord_login: boolean;
  claim_mode: boolean;
  /** 0 = unlimited (matches the rooms column semantics). */
  max_yamls_per_user: number;
  deadline: {
    /** When false, the template applies an empty deadline (no auto-close). */
    enabled: boolean;
    /** "HH:MM" 24h. */
    time_of_day: string;
    /** 0..30. 0 = today (rolls forward to tomorrow if HH:MM has already
     *  passed in the host's local timezone). N>=1 honoured literally. */
    day_offset: number;
  };
  apworld_policy: ApworldPolicy;
  auto_upgrade_apworld_pins: boolean;
}

/** What the modal keeps in state — what the template applies to. */
export interface CreateRoomModalState {
  description: string;
  requireDiscordLogin: boolean;
  claimMode: boolean;
  maxYamlsPerUser: number;
  /** datetime-local string ("YYYY-MM-DDTHH:MM"), or "" for no deadline. */
  deadlineLocal: string;
  policyMode: ApworldPolicy;
  autoUpgrade: boolean;
}

/** A blank starting state — what CreateRoomModal opens with when no template
 *  applies and no host edits have happened yet. */
export const BLANK_MODAL_STATE: CreateRoomModalState = {
  description: "",
  requireDiscordLogin: false,
  claimMode: false,
  maxYamlsPerUser: 0,
  deadlineLocal: "",
  policyMode: "strict",
  autoUpgrade: true,
};

const TWO = (n: number) => n.toString().padStart(2, "0");

/** Format a Date as the value the <input type="datetime-local"> consumes. */
export function dateToLocalInputValue(d: Date): string {
  const y = d.getFullYear();
  const mo = TWO(d.getMonth() + 1);
  const da = TWO(d.getDate());
  const h = TWO(d.getHours());
  const mi = TWO(d.getMinutes());
  return `${y}-${mo}-${da}T${h}:${mi}`;
}

/** Reverse of dateToLocalInputValue — parses "YYYY-MM-DDTHH:MM". Returns
 *  null when the string isn't in that exact shape (defensive against
 *  hand-typed values). */
export function localInputValueToDate(local: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local || "");
  if (!m) return null;
  const [, y, mo, d, h, mi] = m;
  return new Date(
    parseInt(y, 10), parseInt(mo, 10) - 1, parseInt(d, 10),
    parseInt(h, 10), parseInt(mi, 10), 0, 0,
  );
}

/** Compute the absolute deadline a template encodes, relative to `now`.
 *  Returns null when deadline is disabled. Returns the datetime-local
 *  string the input expects (so it's directly assignable to state). */
export function computeDeadlineFromTemplate(
  deadline: RoomTemplatePayload["deadline"],
  now: Date,
): string | null {
  if (!deadline.enabled) return null;
  const m = /^(\d{2}):(\d{2})$/.exec(deadline.time_of_day);
  if (!m) return null;
  const hh = parseInt(m[1], 10);
  const mm = parseInt(m[2], 10);

  // Build candidate: today (local) at HH:MM + N days.
  const candidate = new Date(
    now.getFullYear(), now.getMonth(), now.getDate(),
    hh, mm, 0, 0,
  );
  candidate.setDate(candidate.getDate() + deadline.day_offset);

  // Roll-forward rule: only when day_offset === 0 AND the candidate is in
  // the past. Larger offsets are honoured literally (host explicitly asked
  // for "+N days at HH:MM").
  if (deadline.day_offset === 0 && candidate.getTime() <= now.getTime()) {
    candidate.setDate(candidate.getDate() + 1);
  }
  return dateToLocalInputValue(candidate);
}

/** Round-trip a datetime-local string back to a (time + day_offset) pair
 *  relative to `now`. Used by Save-as-template so the host's chosen absolute
 *  datetime gets stored as the relative intent it implies. Returns
 *  { enabled: false } when the string is empty or unparseable. */
export function deriveTemplateDeadline(
  local: string,
  now: Date,
): RoomTemplatePayload["deadline"] {
  const fallback: RoomTemplatePayload["deadline"] = {
    enabled: false,
    time_of_day: "19:00",
    day_offset: 0,
  };
  if (!local) return fallback;
  const dt = localInputValueToDate(local);
  if (!dt) return fallback;

  // Day offset = day-difference between dt's date and now's date, ignoring
  // wall-clock. Negative offsets (deadline in the past relative to now)
  // collapse to 0 — host can resave later if they care.
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDt = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate());
  const dayMs = 24 * 60 * 60 * 1000;
  const offset = Math.max(0, Math.round((startOfDt.getTime() - startOfToday.getTime()) / dayMs));

  return {
    enabled: true,
    time_of_day: `${TWO(dt.getHours())}:${TWO(dt.getMinutes())}`,
    day_offset: Math.min(30, offset),
  };
}

/** Apply a template's payload to the modal's React state. The deadline
 *  field stays editable after apply — the helper just pre-fills it. */
export function applyTemplateToModal(
  payload: RoomTemplatePayload,
  now: Date,
): CreateRoomModalState {
  return {
    description: payload.description ?? "",
    requireDiscordLogin: !!payload.require_discord_login,
    claimMode: !!payload.claim_mode,
    maxYamlsPerUser: Math.max(0, payload.max_yamls_per_user || 0),
    deadlineLocal: computeDeadlineFromTemplate(payload.deadline, now) ?? "",
    policyMode: payload.apworld_policy ?? "strict",
    autoUpgrade: payload.auto_upgrade_apworld_pins ?? true,
  };
}

/** Capture the modal's current state as a template payload. The deadline
 *  is round-tripped via deriveTemplateDeadline so the relative intent
 *  survives across "today"s. */
export function captureTemplateFromModal(
  state: CreateRoomModalState,
  now: Date,
): RoomTemplatePayload {
  return {
    description: state.description,
    require_discord_login: state.requireDiscordLogin,
    claim_mode: state.claimMode,
    max_yamls_per_user: state.maxYamlsPerUser,
    deadline: deriveTemplateDeadline(state.deadlineLocal, now),
    apworld_policy: state.policyMode,
    auto_upgrade_apworld_pins: state.autoUpgrade,
  };
}
