const BASE = "/api";

// ── Feature flags ─────────────────────────────────────────────────

export interface Features {
  generation: boolean;
}

export async function getFeatures(): Promise<Features> {
  return fetchJson(`${BASE}/features`);
}

export interface PlayerInfo {
  slot: number;
  name: string;
  game: string;
  checks_done: number;
  checks_total: number;
  completion_pct: number;
  client_status: number;
  status_label: string;
  goal_completed: boolean;
}

export interface GameRecord {
  seed: string;
  ap_version: string;
  creation_time: string | null;
  players: PlayerInfo[];
  player_count: number;
  games: string[];
  has_save: boolean;
  zip_path: string | null;
  save_path: string | null;
  patch_files: string[];
  race_mode: number;
  hint_cost: number | null;
  release_mode: string | null;
  collect_mode: string | null;
  spoiler: boolean;
  last_activity: string | null;
  overall_completion_pct: number;
  all_goals_completed: boolean;
  game_versions: Record<string, string>;
}

export interface Summary {
  total_games: number;
  games_with_save: number;
  games_by_frequency: [string, number][];
  players_by_frequency: [string, number][];
  versions: [string, number][];
}

export interface GameFilters {
  game?: string;
  player?: string;
  seed?: string;
  version?: string;
  has_save?: "true" | "false";
  sort?: string;
  limit?: number;
}

export interface ServerInstance {
  seed: string;
  port: number;
  zip_path: string;
  players: string[];
  started_at: string;
  pid: number | null;
  status: string;
  connection_url: string;
  uptime_seconds: number;
  recent_log: string[];
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export async function getGames(filters: GameFilters = {}): Promise<GameRecord[]> {
  const params = new URLSearchParams();
  for (const [key, val] of Object.entries(filters)) {
    if (val !== undefined && val !== "") params.set(key, String(val));
  }
  const qs = params.toString();
  return fetchJson(`${BASE}/games${qs ? `?${qs}` : ""}`);
}

export async function getGame(seed: string): Promise<GameRecord> {
  return fetchJson(`${BASE}/games/${seed}`);
}

export async function getSummary(): Promise<Summary> {
  return fetchJson(`${BASE}/summary`);
}

export async function refreshData(): Promise<{ status: string; count: number }> {
  const res = await fetch(`${BASE}/refresh`, { method: "POST" });
  return res.json();
}

// Server management
export async function getServers(): Promise<ServerInstance[]> {
  return fetchJson(`${BASE}/servers`);
}

export async function getServerStatus(seed: string): Promise<ServerInstance> {
  return fetchJson(`${BASE}/servers/${seed}`);
}

export async function launchServer(seed: string): Promise<ServerInstance> {
  const res = await fetch(`${BASE}/serve/${seed}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to launch server");
  }
  return res.json();
}

export async function sendServerCommand(seed: string, command: string): Promise<void> {
  const res = await fetch(`${BASE}/servers/${seed}/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to send command");
  }
}

export async function stopServer(seed: string): Promise<void> {
  const res = await fetch(`${BASE}/serve/${seed}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to stop server");
}

// Upload
export async function uploadGame(file: File): Promise<{ status: string; filename: string; total_games: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Upload failed");
  }
  return res.json();
}

// APWorlds
export interface APWorldVersion {
  version: string;
  url: string | null;
  local: string | null;
  sha256: string | null;
  source: "url" | "local" | "builtin";
}

export interface APWorldInfo {
  name: string;
  display_name: string;
  game_name: string;  // matches YAML.game (FEAT-21 lookup key)
  home: string;
  tags: string[];
  supported: boolean;
  disabled: boolean;
  is_builtin: boolean;
  has_update: boolean;
  versions: APWorldVersion[];
  downloadable_versions: { version: string }[];
}

export interface InstalledAPWorld {
  filename: string;
  name: string;
  path: string;
  version?: string;
}

// FEAT-21: per-room APWorld pin shape returned by /api/rooms/<id>/apworlds
// (host view). The public endpoint returns the same shape with
// available_versions=[] and only games that have a selected_version set.
export interface RoomAPWorldEntry {
  game: string;                 // raw YAML.game string
  yaml_count: number;
  in_index: boolean;
  apworld_name: string | null;  // index key, null if game not in index
  display_name: string;
  home: string;
  tags: string[];
  selected_version: string | null;
  download_url: string | null;
  available_versions: {
    version: string;
    source: "url" | "local" | "builtin";
    sha256: string | null;
    url: string | null;
  }[];
  /** FEAT-21: room-level policy steering the public copy.
   *   "required"  -> "you need to install this version"
   *   "suggested" -> "the host suggests this version"
   * Mirrored from room.allow_mixed_apworld_versions on the backend. */
  policy: "required" | "suggested";
  /** FEAT-21: true when room.force_latest_apworld_versions is on, in which
   *  case `selected_version` is the index's latest (computed each request)
   *  and the host picker disables manual pinning. */
  auto_latest: boolean;
}

export async function getAPWorlds(search?: string): Promise<APWorldInfo[]> {
  const params = search ? `?search=${encodeURIComponent(search)}` : "";
  return fetchJson(`${BASE}/apworlds${params}`);
}

export async function getInstalledAPWorlds(): Promise<InstalledAPWorld[]> {
  return fetchJson(`${BASE}/apworlds/installed`);
}

export async function installAPWorld(name: string, version?: string): Promise<{ status: string; name: string; version: string }> {
  const res = await fetch(`${BASE}/apworlds/install`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, version }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Install failed");
  }
  return res.json();
}

export async function removeAPWorld(name: string): Promise<void> {
  const res = await fetch(`${BASE}/apworlds/${name}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove APWorld");
}

export async function refreshAPWorldIndex(): Promise<{ status: string; count: number }> {
  const res = await fetch(`${BASE}/apworlds/refresh`, { method: "POST" });
  return res.json();
}

export async function getRoomAPWorlds(roomId: string): Promise<RoomAPWorldEntry[]> {
  return fetchJson(`${BASE}/rooms/${roomId}/apworlds`);
}

export async function setRoomAPWorld(roomId: string, apworldName: string, version: string | null): Promise<void> {
  const res = await fetch(`${BASE}/rooms/${roomId}/apworlds/${encodeURIComponent(apworldName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to save APWorld pin");
  }
}

export async function getPublicRoomAPWorlds(roomId: string): Promise<RoomAPWorldEntry[]> {
  return fetchJson(`${BASE}/public/rooms/${roomId}/apworlds`);
}

export interface AutoPinAllResult {
  pinned: string[];
  /** FEAT-28 v2: pins existing at a lower version that got bumped up
   *  to a higher YAML-declared version. Empty unless the room flag
   *  `auto_upgrade_apworld_pins` is on. */
  upgraded?: string[];
  /** Subset of `pinned`/`upgraded` where the version was taken from a
   *  YAML's `requires.game.<Name>` declaration rather than falling back
   *  to the index's latest. Lets the host see at a glance how much of
   *  the auto-pin was YAML-driven. */
  pinned_with_yaml_version: string[];
  skipped_already_pinned: string[];
  /** FEAT-28 v2: pin exists and the auto-upgrade toggle is off, so the
   *  endpoint declined to overwrite even though a higher version would
   *  apply. Empty when the toggle is on (the default). */
  skipped_locked?: string[];
  /** FEAT-28 v2: in the index as a built-in stub - no downloadable
   *  APWorld because the game ships with AP core. Player needs nothing
   *  extra installed. Distinguished from `skipped_not_in_index` so the
   *  host can tell "covered by AP core" from "genuinely missing entry,
   *  worth contributing upstream". */
  skipped_builtin?: string[];
  skipped_not_in_index: string[];
}

export async function autoPinAllAPWorlds(roomId: string): Promise<AutoPinAllResult> {
  const res = await fetch(`${BASE}/rooms/${roomId}/apworlds/auto-pin-all`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Auto-pin failed");
  }
  return res.json();
}

// Auth
export interface AuthUser {
  id: number;
  discord_id: string;
  discord_username: string;
  is_admin: boolean;
  is_approved: boolean;
  /** Derived server-side from Discord ID match against AP_OWNER_DISCORD_ID.
   *  Used only to gate the owner-only "view as" toggle (DEVEX-02);
   *  is_admin remains the canonical authorization flag for every
   *  other gate. Older /api/auth/me responses (pre-2026-05-04) may
   *  omit this; treat undefined as false. */
  is_owner?: boolean;
  created_at: string;
}

export async function getAuthMe(): Promise<AuthUser> {
  return fetchJson(`${BASE}/auth/me`);
}

// Market (legacy seed-based)
export interface MarketListing {
  id: number;
  seed: string | null;
  tracker_id: string | null;
  slot: number;
  player_name: string;
  item_name: string;
  listing_type: "offer" | "request";
  quantity: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MarketMatch {
  offer_id: number;
  offer_player: string;
  offer_slot: number;
  request_id: number;
  request_player: string;
  request_slot: number;
  item_name: string;
  offer_qty: number;
  request_qty: number;
}

export async function getMarketListings(seed: string): Promise<MarketListing[]> {
  return fetchJson(`${BASE}/market/${seed}`);
}

export async function getMarketMatches(seed: string): Promise<MarketMatch[]> {
  return fetchJson(`${BASE}/market/${seed}/matches`);
}

export async function createListing(seed: string, data: {
  slot: number; player_name: string; item_name: string; listing_type: string; quantity?: number;
}): Promise<MarketListing> {
  const res = await fetch(`${BASE}/market/${seed}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to create listing");
  }
  return res.json();
}

export async function updateListing(seed: string, id: number, data: { status?: string; quantity?: number }): Promise<MarketListing> {
  const res = await fetch(`${BASE}/market/${seed}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteListing(seed: string, id: number): Promise<void> {
  await fetch(`${BASE}/market/${seed}/${id}`, { method: "DELETE" });
}

// Trackers
export interface TrackerInfo {
  id: string;
  tracker_url: string;
  display_name: string;
  host: string;
  port: number | null;
  created_at: string;
  last_synced: string | null;
}

export interface TrackerDetail extends TrackerInfo {
  tracker_data: {
    room_id?: string;
    host?: string;
    players: { slot: number; name: string; game: string; checks_done?: number; checks_total?: number; status?: number }[];
    player_count: number;
    games: string[];
    error?: string;
  };
}

export async function getTrackers(limit?: number): Promise<TrackerInfo[]> {
  const qs = limit ? `?limit=${limit}` : "";
  return fetchJson(`${BASE}/trackers${qs}`);
}

export async function registerTracker(tracker_url: string, display_name?: string): Promise<TrackerDetail> {
  const res = await fetch(`${BASE}/trackers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tracker_url, display_name }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to register tracker");
  }
  return res.json();
}

export async function getTrackerInfo(trackerId: string): Promise<TrackerDetail> {
  return fetchJson(`${BASE}/trackers/${trackerId}`);
}

export async function getTrackerListings(trackerId: string, status?: string): Promise<MarketListing[]> {
  const qs = status ? `?status=${status}` : "";
  return fetchJson(`${BASE}/trackers/${trackerId}/listings${qs}`);
}

export async function getTrackerMatches(trackerId: string): Promise<MarketMatch[]> {
  return fetchJson(`${BASE}/trackers/${trackerId}/matches`);
}

export async function createTrackerListing(trackerId: string, data: {
  slot: number; player_name: string; item_name: string; listing_type: string; quantity?: number;
}): Promise<MarketListing> {
  const res = await fetch(`${BASE}/trackers/${trackerId}/listings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "Failed to create listing");
  }
  return res.json();
}

export async function updateTrackerListing(trackerId: string, id: number, data: { status?: string; quantity?: number }): Promise<MarketListing> {
  const res = await fetch(`${BASE}/trackers/${trackerId}/listings/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteTrackerListing(trackerId: string, id: number): Promise<void> {
  await fetch(`${BASE}/trackers/${trackerId}/listings/${id}`, { method: "DELETE" });
}

// Rooms
export interface Room {
  id: string;
  name: string;
  description: string;
  host_name: string;
  host_user_id: number | null;
  status: string;
  seed: string | null;
  generation_log: string | null;
  spoiler_level: number;
  race_mode: boolean;
  max_players: number;
  /** FEAT-07: per-Discord-user submission cap (0 = unlimited).
   *  Enforced only on logged-in submits via /api/submit. */
  max_yamls_per_user: number;
  external_host: string | null;
  external_port: number | null;
  require_discord_login: boolean;
  /** FEAT-04: optional ISO 8601 UTC timestamp at which the sweeper auto-closes
   *  the room. NULL = no scheduled close (manual "Close Room" still works). */
  submit_deadline: string | null;
  /** FEAT-08: optional external Archipelago tracker URL. When set, both
   *  RoomDetail and RoomPublic surface LiveTracker against that URL. */
  tracker_url: string | null;
  /** FEAT-17: optional override for the in-game slot name the WebSocket
   *  TrackerConnection authenticates as. NULL = auto-discover (host's
   *  own first-uploaded slot via room_yamls.submitter_user_id, falling
   *  back to scraping the first slot from the tracker page). Setting an
   *  explicit value bypasses both auto-discovery paths. */
  tracker_slot_name: string | null;
  /** FEAT-20: when true, host bulk-uploads land as anonymous and players
   *  in the public lobby get a "Claim this slot" button. Default false. */
  claim_mode: boolean;
  /** FEAT-21: softens "required" -> "suggested" copy on the public install
   *  panel. Lets groups that don't strictly enforce same-version play
   *  avoid scaring players away with a hard mismatch warning. */
  allow_mixed_apworld_versions: boolean;
  /** FEAT-21: ignores stored per-game pins, always surfaces the latest
   *  index version per game. Auto-bumps as the index updates. The host
   *  picker disables the dropdowns when this is on. */
  force_latest_apworld_versions: boolean;
  /** FEAT-28 v2: when true (default), auto-pin upgrades the room's
   *  pin to the highest indexed APWorld version any YAML in the room
   *  declares via `requires.game.<Name>`. Hosts who want to lock pins
   *  flip this off. */
  auto_upgrade_apworld_pins: boolean;
  created_at: string;
  updated_at: string;
  yamls?: RoomYaml[];
  activity?: RoomActivity[];
  /** Server-side aggregate count of room_yamls for this room. Returned
   *  by GET /api/rooms (the list view) as a cheap COUNT subquery so the
   *  table can render slot counts without fetching the full yaml array
   *  per row. Single-room reads (GET /api/rooms/<id>) return the full
   *  `yamls` array instead and may omit this. */
  yaml_count?: number;
}

export type ValidationStatus =
  | "validated"
  | "manually_validated"
  | "unsupported"
  | "failed"
  | "unknown";

export interface RoomYaml {
  id: number;
  room_id: string;
  player_name: string;
  game: string;
  filename: string;
  validation_status: ValidationStatus;
  validation_error: string | null;
  uploaded_at: string;
  /** Set on host-side reads when the submitter was logged in. Public reads
   *  never include this - it's host-only by design. */
  submitter_username?: string | null;
  /** FEAT-28 v2: cached `{game_name: version}` map from the YAML's
   *  `requires.game` block. Null when the YAML doesn't declare versions
   *  or hasn't been parsed yet (legacy rows - the auto-pin-all button
   *  backfills these). Used by the room overview's Version column to
   *  render orange-warn cells when a YAML's declared version disagrees
   *  with the room's current pin. */
  apworld_versions?: Record<string, string> | null;
}

export async function setYamlValidation(
  roomId: string,
  yamlId: number,
  status: ValidationStatus,
  error?: string,
): Promise<RoomYaml> {
  const res = await fetch(`${BASE}/rooms/${roomId}/yamls/${yamlId}/validation`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, error }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

export async function getRooms(
  status?: string,
  asUser?: number,
): Promise<Room[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (asUser !== undefined) params.set("as_user", String(asUser));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return fetchJson(`${BASE}/rooms${qs}`);
}

export async function getRoom(id: string): Promise<Room> {
  return fetchJson(`${BASE}/rooms/${id}`);
}

export async function createRoom(data: {
  name: string; host_name: string; description?: string;
  spoiler_level?: number; race_mode?: boolean; max_players?: number;
  require_discord_login?: boolean;
  /** ISO 8601 UTC string (Date.toISOString()) for FEAT-04 auto-close. */
  submit_deadline?: string | null;
  /** FEAT-07: 0 means unlimited. */
  max_yamls_per_user?: number;
  /** FEAT-08: Archipelago tracker URL. */
  tracker_url?: string | null;
  /** FEAT-21 policy radio: strict (both false), flexible (allow_mixed
   *  only), latest (force_latest only). Caller sends both display
   *  flags atomically so the room never lands in a transient
   *  (force=true, mixed=true) state. */
  allow_mixed_apworld_versions?: boolean;
  force_latest_apworld_versions?: boolean;
  /** FEAT-28 v2: defaults to true server-side; pass false to lock pins. */
  auto_upgrade_apworld_pins?: boolean;
}): Promise<Room> {
  const res = await fetch(`${BASE}/rooms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

export async function deleteRoom(id: string): Promise<void> {
  await fetch(`${BASE}/rooms/${id}`, { method: "DELETE" });
}

export async function updateRoom(id: string, data: Partial<{
  name: string; description: string; spoiler_level: number; race_mode: boolean;
  max_players: number; external_host: string | null; external_port: number | null;
  require_discord_login: boolean;
  /** ISO 8601 UTC string for FEAT-04, or null/empty string to clear the deadline. */
  submit_deadline: string | null;
  /** FEAT-07: 0 means unlimited. */
  max_yamls_per_user: number;
  /** FEAT-08: empty string or null clears the URL. */
  tracker_url: string | null;
  /** FEAT-17: explicit slot-name override for the WebSocket tracker
   *  connection. Empty string or null clears the override (revert to
   *  auto-discovery). */
  tracker_slot_name: string | null;
  /** FEAT-20: opt-in claim-mode toggle for this room. */
  claim_mode: boolean;
  /** FEAT-21 toggles. See Room type for semantics. */
  allow_mixed_apworld_versions: boolean;
  force_latest_apworld_versions: boolean;
  /** FEAT-28 v2 toggle. See Room type for semantics. */
  auto_upgrade_apworld_pins: boolean;
}>): Promise<Room> {
  const res = await fetch(`${BASE}/rooms/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

export async function uploadYaml(roomId: string, file: File): Promise<RoomYaml> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/rooms/${roomId}/yamls`, { method: "POST", body: form });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

export async function removeYaml(roomId: string, yamlId: number): Promise<void> {
  await fetch(`${BASE}/rooms/${roomId}/yamls/${yamlId}`, { method: "DELETE" });
}

export async function closeRoom(id: string): Promise<Room> {
  const res = await fetch(`${BASE}/rooms/${id}/close`, { method: "POST" });
  return res.json();
}

export async function reopenRoom(id: string): Promise<Room> {
  const res = await fetch(`${BASE}/rooms/${id}/reopen`, { method: "POST" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Failed to reopen room");
  }
  return res.json();
}

export interface GenerationJob {
  id: number;
  room_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  seed: string | null;
  log: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface GenerationJobNone {
  status: "none";
}

export interface EnqueueGenerationResult {
  status: "queued" | "already_running";
  job_id: number;
  job_status: GenerationJob["status"];
}

export async function generateRoom(id: string): Promise<EnqueueGenerationResult> {
  const res = await fetch(`${BASE}/rooms/${id}/generate`, { method: "POST" });
  if (res.status === 202 || res.status === 409) {
    return res.json();
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Generate failed: ${res.status}`);
  }
  return res.json();
}

export async function getGenerationJob(roomId: string, jobId: number): Promise<GenerationJob> {
  return fetchJson(`${BASE}/rooms/${roomId}/generation/${jobId}`);
}

export async function getLatestGenerationJob(roomId: string): Promise<GenerationJob | GenerationJobNone> {
  return fetchJson(`${BASE}/rooms/${roomId}/generation/latest`);
}

export async function launchRoom(id: string): Promise<ServerInstance> {
  const res = await fetch(`${BASE}/rooms/${id}/launch`, { method: "POST" });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

export async function stopRoom(id: string): Promise<void> {
  const res = await fetch(`${BASE}/rooms/${id}/stop`, { method: "POST" });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
}

export async function getRoomPatches(id: string): Promise<string[]> {
  return fetchJson(`${BASE}/rooms/${id}/patches`);
}

export async function getRoomSpoiler(id: string): Promise<{ filename: string; content: string }> {
  return fetchJson(`${BASE}/rooms/${id}/spoiler`);
}

export async function testGenerateRoom(id: string): Promise<{ success: boolean; error?: string; log?: string }> {
  const res = await fetch(`${BASE}/rooms/${id}/test-generate`, { method: "POST" });
  return res.json();
}

export interface RoomActivity {
  id: number;
  room_id: string;
  event_type: string;
  message: string;
  created_at: string;
}

// Room Tracker
export interface RoomTrackerData {
  status: string;
  has_save: boolean;
  seed: string;
  server_status: string;
  connection_url: string;
  players: PlayerInfo[];
  overall_completion_pct: number;
  total_checks_done: number;
  total_checks_total: number;
  goals_completed: number;
  goals_total: number;
  all_goals_completed: boolean;
  last_activity: string | null;
  /** FEAT-17 V1.4: tells the UI whether the response is HTML-only
   *  ("external"), HTML augmented with live WebSocket data
   *  ("external+ws"), or local apsave parse (no `source` field set).
   *  Used to decide whether to surface a "live" badge. */
  source?: string;
}

export async function getRoomTracker(roomId: string): Promise<RoomTrackerData> {
  return fetchJson(`${BASE}/rooms/${roomId}/tracker`);
}

/** FEAT-08: public mirror of getRoomTracker, used by RoomPublic. Returns
 *  the same RoomTrackerData shape but only for external archipelago.gg
 *  trackers (`{status: "no_tracker"}` when the room has no tracker_url set). */
export async function getPublicRoomTracker(roomId: string): Promise<RoomTrackerData | { status: "no_tracker" }> {
  return fetchJson(`${BASE}/public/rooms/${roomId}/tracker`);
}

// FEAT-14: per-slot detail fetched on modal open. Errors surface as
// `error` in the response body; the modal renders an error state.
export interface SlotItemReceived {
  item: string;
  amount: number;
  last_order: number;
}
export interface SlotLocation {
  location: string;
  checked: boolean;
}
export interface SlotHint {
  finder: string;
  receiver: string;
  item: string;
  location: string;
  game: string;
  entrance: string;
  found: boolean;
}
export interface SlotDetail {
  team: number;
  slot: number;
  name: string | null;
  items_received: SlotItemReceived[];
  locations: SlotLocation[];
  hints: SlotHint[];
  tracker_url: string;
  /** Owner attribution. Always present on the host route; only present on
   *  the public route when the requester has a session (FEAT-13 rule). */
  submitter_user_id?: number | null;
  submitter_username?: string | null;
  /** FEAT-17 V1.4: live WebSocket overlay fields. Present when the
   *  tracker_ws subsystem is connected for this room. */
  client_status?: number;
  status_label?: string;
  goal_completed?: boolean;
  /** "ws" when hints came from the live WebSocket cache (subscribed via
   *  SetNotify, real-time), "html" when fell back to the archipelago.gg
   *  HTML scrape (60s TTL). Absent when WS not connected at all. */
  hints_source?: "ws" | "html";
}
export type SlotDetailResponse = SlotDetail | { error: string };

export async function getRoomSlotTracker(
  roomId: string, slot: number, team = 0,
): Promise<SlotDetailResponse> {
  return fetchJson(`${BASE}/rooms/${roomId}/tracker/slot/${slot}?team=${team}`);
}

export async function getPublicRoomSlotTracker(
  roomId: string, slot: number, team = 0,
): Promise<SlotDetailResponse> {
  return fetchJson(`${BASE}/public/rooms/${roomId}/tracker/slot/${slot}?team=${team}`);
}

// ── FEAT-17 V1.5: in-game activity stream (PrintJSON) ─────────────

/** One PrintJSON event from the AP server. `text` is a fully-resolved,
 *  human-readable rendering of the message (item / location / player IDs
 *  resolved via the DataPackage cache). Raw fields kept for clients that
 *  want to render their own structured view (icons per type, etc.). */
export interface ActivityEvent {
  ts: number;
  type: string;
  text: string;
  tags: string[];
  team: number | null;
  slot: number | null;
  receiving: number | null;
  /** Present on ItemSend events: { item, location, player, flags }
   *  where `player` is the FINDER slot. */
  item: { item: number; location: number; player: number; flags: number } | null;
  found: boolean | null;
}

export interface ActivityStreamResponse {
  /** "ok" while the WebSocket is connected; "no_connection" when the
   *  tracker_ws subsystem isn't holding a connection for this room. */
  status: string;
  /** Server-side `time.time()` at response. Pass back as `?since=` to
   *  poll for new events without re-fetching the entire buffer. */
  now?: number;
  events: ActivityEvent[];
}

export async function getRoomActivityStream(
  roomId: string, since?: number, limit = 200,
): Promise<ActivityStreamResponse> {
  const params = new URLSearchParams();
  if (since !== undefined) params.set("since", String(since));
  if (limit !== 200) params.set("limit", String(limit));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return fetchJson(`${BASE}/rooms/${roomId}/activity-stream${qs}`);
}

export async function getPublicRoomActivityStream(
  roomId: string, since?: number, limit = 200,
): Promise<ActivityStreamResponse> {
  const params = new URLSearchParams();
  if (since !== undefined) params.set("since", String(since));
  if (limit !== 200) params.set("limit", String(limit));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return fetchJson(`${BASE}/public/rooms/${roomId}/activity-stream${qs}`);
}

// Item-level tracker
export interface ReceivedItem {
  item_name: string;
  item_id: number;
  sender_name: string;
  location_name: string;
  flags: number;
  classification: "progression" | "useful" | "filler" | "trap";
}

export interface PlayerItems {
  slot: number;
  name: string;
  game: string;
  received_items: ReceivedItem[];
  item_counts: { progression: number; useful: number; filler: number; trap: number };
}

export interface ItemTrackerData {
  status: string;
  has_datapackage: boolean;
  players: PlayerItems[];
}

export async function getRoomItemTracker(roomId: string): Promise<ItemTrackerData> {
  return fetchJson(`${BASE}/rooms/${roomId}/tracker/items`);
}

// Templates
export interface TemplateListItem {
  game: string;
  filename: string;
}

export interface TemplateOption {
  name: string;
  type: "choice" | "toggle" | "range" | "list" | "dict";
  description: string;
  category: string;
  default: any;
  choices?: string[];
  min?: number;
  max?: number;
  named_values?: Record<string, number> | null;
}

export interface ParsedTemplate {
  game: string;
  ap_version: string;
  world_version: string;
  categories: string[];
  options: TemplateOption[];
}

export async function getTemplateList(): Promise<TemplateListItem[]> {
  return fetchJson(`${BASE}/templates`);
}

export async function getTemplate(game: string): Promise<ParsedTemplate> {
  return fetchJson(`${BASE}/templates/${encodeURIComponent(game)}`);
}

export async function createYamlFromEditor(roomId: string, data: {
  player_name: string; game: string; yaml_content: string;
}): Promise<RoomYaml> {
  const res = await fetch(`${BASE}/rooms/${roomId}/yamls/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

// Admin
export async function getAdminUsers(): Promise<AuthUser[]> {
  return fetchJson(`${BASE}/admin/users`);
}

export async function setUserApproval(userId: number, approved: boolean): Promise<AuthUser> {
  const res = await fetch(`${BASE}/admin/users/${userId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.error); }
  return res.json();
}

// ── Public room landing + YAML submission ─────────────────────────

export interface PublicRoomYaml {
  filename: string;
  id: number;
  player_name: string;
  game: string;
  validation_status: ValidationStatus;
  validation_error: string | null;
  uploaded_at: string | null;
  /** FEAT-13: present only when the requester is logged in. Null for
   *  anonymous submits, the Discord display name otherwise. */
  submitter_username?: string | null;
  /** FEAT-20: present only when the requester is logged in. Null for
   *  unclaimed slots in claim-mode rooms (and anonymous submits in
   *  regular rooms). The numeric id lets the frontend reliably check
   *  "did *I* claim this?" against AuthUser.id without a brittle
   *  username equality check. */
  submitter_user_id?: number | null;
  /** FEAT-28 v2: cached `{game_name: version}` map from the YAML's
   *  `requires.game` block. See RoomYaml for full semantics. */
  apworld_versions?: Record<string, string> | null;
}

export interface PublicRoom {
  id: string;
  name: string;
  description: string;
  status: string;
  host_name: string;
  seed: string | null;
  external_host: string | null;
  external_port: number | null;
  max_players: number;
  /** FEAT-07: visible to players so they understand the cap they face. */
  max_yamls_per_user: number;
  race_mode: boolean;
  spoiler_level: number;
  require_discord_login: boolean;
  /** FEAT-04: ISO 8601 UTC. Player-visible so they know when to drop YAMLs. */
  submit_deadline: string | null;
  /** FEAT-08: external archipelago.gg tracker URL the host pasted. */
  tracker_url: string | null;
  /** FEAT-20: opt-in claim-mode flag. Drives the lobby UI to show Claim/
   *  Release buttons and "Unclaimed" badges instead of normal upload row. */
  claim_mode: boolean;
  /** FEAT-21: see Room type for semantics. Public copy on the install
   *  panel reads off these flags. */
  allow_mixed_apworld_versions: boolean;
  force_latest_apworld_versions: boolean;
  /** FEAT-28 v2: see Room. Public reads it so the version-warning
   *  column on the public room can match host-side behaviour. */
  auto_upgrade_apworld_pins: boolean;
  created_at: string | null;
  yamls: PublicRoomYaml[];
  player_count: number;
}

export async function getPublicRoom(id: string): Promise<PublicRoom> {
  return fetchJson(`${BASE}/public/rooms/${id}`);
}

export interface PublicRoomYamlDetail extends PublicRoomYaml {
  yaml_content: string;
}

export async function getPublicRoomYaml(roomId: string, yamlId: number): Promise<PublicRoomYamlDetail> {
  return fetchJson(`${BASE}/public/rooms/${roomId}/yamls/${yamlId}`);
}

/** FEAT-13: a logged-in submitter deleting their own row from /r/<id>.
 *  Server enforces session present, submitter_user_id match, and room.status == open. */
export async function deletePublicYaml(roomId: string, yamlId: number): Promise<void> {
  const res = await fetch(`${BASE}/public/rooms/${roomId}/yamls/${yamlId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Failed to delete YAML");
  }
}

/** FEAT-20: claim an unclaimed slot in a claim-mode room. Server enforces
 *  session, room.claim_mode, room.status == open, atomic claim, and
 *  per-user cap (max_yamls_per_user). 409 means somebody beat you to it. */
export interface ClaimResult {
  status: "claimed";
  yaml_id: number;
  submitter_user_id: number;
  submitter_username: string;
}

export async function claimYaml(roomId: string, yamlId: number): Promise<ClaimResult> {
  const res = await fetch(`${BASE}/public/rooms/${roomId}/yamls/${yamlId}/claim`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Claim failed: ${res.status}`);
  }
  return res.json();
}

/** FEAT-20: release a slot you've claimed back to the unclaimed pool.
 *  Atomic on submitter_user_id == requester so you can never release
 *  someone else's claim. */
export async function releaseYaml(roomId: string, yamlId: number): Promise<void> {
  const res = await fetch(`${BASE}/public/rooms/${roomId}/yamls/${yamlId}/release`, {
    method: "POST",
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Failed to release claim");
  }
}

/** FEAT-18: a logged-in submitter updating their own YAML in place
 *  (vs the delete-then-resubmit churn). Same auth model as deletePublicYaml.
 *  Accepts either a File (multipart upload) or a string of raw YAML content. */
export interface UpdateYamlResult extends SubmitResult {
  /** True when the new YAML's `name:` differs from the old row's player_name. */
  renamed: boolean;
  /** Set when `renamed` is true; the player_name the row had before this
   *  update. Lets the UI surface "your slot is now <new>". */
  previous_player_name: string | null;
}

export async function updatePublicYaml(
  roomId: string,
  yamlId: number,
  payload: File | string,
): Promise<UpdateYamlResult> {
  const init: RequestInit = { method: "PUT" };
  if (payload instanceof File) {
    const form = new FormData();
    form.append("file", payload);
    init.body = form;
  } else {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify({ yaml_content: payload });
  }
  const res = await fetch(`${BASE}/public/rooms/${roomId}/yamls/${yamlId}`, init);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Update failed: ${res.status}`);
  }
  return res.json();
}

/** FEAT-18 host variant: room host updates any YAML in their room.
 *  Auth-gated by the existing room ownership middleware (must be the
 *  host or an admin). Same body shape as updatePublicYaml. */
export async function updateRoomYaml(
  roomId: string,
  yamlId: number,
  payload: File | string,
): Promise<UpdateYamlResult> {
  const init: RequestInit = { method: "PUT" };
  if (payload instanceof File) {
    const form = new FormData();
    form.append("file", payload);
    init.body = form;
  } else {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify({ yaml_content: payload });
  }
  const res = await fetch(`${BASE}/rooms/${roomId}/yamls/${yamlId}`, init);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Update failed: ${res.status}`);
  }
  return res.json();
}

export interface SubmitResult {
  id: number;
  player_name: string;
  game: string;
  validation_status: ValidationStatus;
  validation_error: string | null;
}

export async function submitYamlToRoom(roomId: string, file: File): Promise<SubmitResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/submit/${roomId}`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Submission failed: ${res.status}`);
  }
  return res.json();
}

export async function submitYamlContentToRoom(
  roomId: string,
  yaml_content: string,
): Promise<SubmitResult> {
  const res = await fetch(`${BASE}/submit/${roomId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yaml_content }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Submission failed: ${res.status}`);
  }
  return res.json();
}

// ── Public player-connect info ────────────────────────────────────
export interface ConnectPlayer {
  slot: number;
  name: string;
  game: string;
}

export interface ConnectServerInfo {
  status: "starting" | "running" | "stopped" | "crashed" | "never_started" | "external";
  host?: string;
  port?: number;
  connection_url?: string;
  started_at?: string;
}

export interface ConnectInfo {
  seed: string;
  ap_version: string;
  creation_time: string | null;
  player_count: number;
  players: ConnectPlayer[];
  patch_files: string[];
  has_zip: boolean;
  server: ConnectServerInfo;
}

export async function getConnectInfo(seed: string): Promise<ConnectInfo> {
  return fetchJson(`${BASE}/connect/${encodeURIComponent(seed)}`);
}

export function connectDownloadUrl(seed: string): string {
  return `${BASE}/connect/${encodeURIComponent(seed)}/download`;
}

export function connectPatchDownloadUrl(seed: string, filename: string): string {
  return `${BASE}/connect/${encodeURIComponent(seed)}/patches/${encodeURIComponent(filename)}`;
}
