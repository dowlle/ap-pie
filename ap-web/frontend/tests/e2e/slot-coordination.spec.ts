import { expect, test, type Page } from "@playwright/test";

async function fixture(page: Page, role: "owner" | "host" | "anonymous") {
  const host = role === "host";
  const room = { id: "coord-room", name: "Coordination room", host_name: "Host", status: "playing",
    seed: null, yamls: [], player_count: 0, max_players: 0,
    tracker_url: "https://archipelago.gg/tracker/fixture", apworld_versions: {},
    viewer_capabilities: { can_manage_room: host, can_submit: false } };
  const state = { team: 0, slot: 1, player_name: "Player", game: "Super Metroid", claimed: true,
    is_mine: role === "owner", can_edit: role !== "anonymous", owner_username: null,
    bk_since: null as string | null, bk_confirmed_at: null as string | null, go_mode_since: null as string | null,
    slot_note: "", updated_by_username: null as string | null, state_updated_at: null as string | null };
  const players = [1, 2].map((slot) => ({ slot, name: slot === 1 ? "Player" : "Other", game: "Super Metroid",
    checks_done: 2, checks_total: 10, completion_pct: 20, status_label: "playing", goal_completed: false }));
  const writes: unknown[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ json: body, status });
    if (path === "/api/auth/me") return json(role === "anonymous" ? {} : {
      id: host ? 42 : 7, discord_username: host ? "Host" : "Owner", is_approved: true,
    }, role === "anonymous" ? 401 : 200);
    if (path === "/api/features") return json({ generation: false });
    if (path === "/api/deployment") return json({ label: "" });
    if (path.endsWith("/coord-room")) return json(room);
    if (path.endsWith("/tracker")) return json({ status: "ok", source: "external", server_status: "external",
      connection_url: null, players, total_checks_done: 4, total_checks_total: 20, overall_completion_pct: 20,
      goals_completed: 0, goals_total: 2, has_save: true });
    if (path.endsWith("/slots")) return json({ associated: true, slots: [state], activity: [] });
    if (path.endsWith("/tracker/slot/1")) return json({ team: 0, slot: 1, name: "Player",
      items_received: [], locations: [], hints: [], coordination: state });
    if (path.endsWith("/state")) {
      const body = route.request().postDataJSON();
      writes.push(body);
      if (body.bk_action === "set") state.bk_since = new Date().toISOString();
      if (body.bk_action === "clear") state.bk_since = null;
      if (body.go_mode !== undefined) state.go_mode_since = body.go_mode ? new Date().toISOString() : null;
      if (body.slot_note !== undefined) state.slot_note = body.slot_note;
      state.updated_by_username = host ? "Host" : "Owner";
      state.state_updated_at = new Date().toISOString();
      return json(state);
    }
    if (path.endsWith("/activity-stream")) return json({ status: "no_connection", events: [] });
    return json([]);
  });
  return { state, writes };
}

for (const path of ["/r/coord-room", "/rooms/coord-room"]) {
  test(`coordination updates without reload on ${path}`, async ({ page }) => {
    await page.clock.install();
    const { state } = await fixture(page, "host");
    await page.goto(path);
    const card = page.getByRole("button", { name: "Open detail for Player (Super Metroid)", exact: true });
    await card.click();
    await page.getByRole("tab", { name: "Coordination", exact: true }).click();
    await page.getByRole("button", { name: "I am BK", exact: true }).click();
    await expect(page.getByRole("button", { name: "Still BK", exact: true })).toBeVisible();
    await expect(page.getByText(/by @Host/)).toBeVisible();
    await page.getByRole("button", { name: "Enter go mode", exact: true }).click();
    await page.getByRole("textbox", { name: "Slot note", exact: true }).fill("Waiting for Morph Ball");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.getByRole("button", { name: "Save note", exact: true })).toBeDisabled();
    // Another viewer's update is read by the existing tracker poll, even with the modal open.
    state.bk_since = null;
    state.go_mode_since = null;
    await page.clock.fastForward(16_000);
    await expect(page.getByRole("button", { name: "I am BK", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Enter go mode", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).last().click();
    await page.getByRole("button", { name: "BK", exact: true }).click();
    await expect(card).toHaveCount(0);
    state.bk_since = new Date().toISOString();
    await page.clock.fastForward(16_000);
    await expect(card).toBeVisible();
    await expect(card.getByText(/BK <1m/)).toBeVisible();
    await expect(card.getByText("Note", { exact: true })).toHaveAttribute("title", "Waiting for Morph Ball");
    await page.getByRole("button", { name: "Go mode", exact: true }).click();
    await expect(card).toHaveCount(0);
  });
}

test("anonymous coordination is read-only", async ({ page }) => {
  const { state, writes } = await fixture(page, "anonymous");
  state.slot_note = "Waiting for Morph Ball";
  await page.goto("/r/coord-room");
  await page.getByRole("button", { name: "Open detail for Player (Super Metroid)", exact: true }).click();
  await page.getByRole("tab", { name: "Coordination", exact: true }).click();
  await expect(page.getByText("Waiting for Morph Ball", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "I am BK", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Enter go mode", exact: true })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Slot note", exact: true })).toHaveCount(0);
  expect(writes).toEqual([]);
});

test("slot owner has coordination controls in the participant view", async ({ page }) => {
  const { writes } = await fixture(page, "owner");
  await page.goto("/r/coord-room");
  await page.getByRole("button", { name: "Open detail for Player (Super Metroid)", exact: true }).click();
  await page.getByRole("tab", { name: "Coordination", exact: true }).click();
  await page.getByRole("button", { name: "I am BK", exact: true }).click();
  await expect(page.getByRole("button", { name: "Still BK", exact: true })).toBeVisible();
  expect(writes).toEqual([{ bk_action: "set" }]);
});
