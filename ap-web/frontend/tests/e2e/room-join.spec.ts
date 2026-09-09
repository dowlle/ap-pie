import { expect, test, type Page } from "@playwright/test";
import { gameJoinUrl } from "../../src/lib/gameJoin";

const slotName = "Appie's Poké + & #1";
async function mockRoom(page: Page, host = false, connection = "archipelago.gg:38281") {
  const room = { id: "join-room", name: "Join fixture", host_name: "Host", host_user_id: 42,
    status: "playing", seed: null, yamls: [], player_count: 2, max_players: 0,
    tracker_url: "https://archipelago.gg/tracker/fixture", external_host: "archipelago.gg", external_port: 38281,
    viewer_capabilities: { can_manage_room: host, can_submit: false }, apworld_versions: {} };
  const players = ["Pokepelago", "Crash Team Racing"].map((game, index) => ({
    slot: index + 1, name: index ? "CTR player" : slotName, connect_name: index ? "CTR player" : slotName, game, checks_done: 2, checks_total: 10,
    completion_pct: 20, status_label: "playing", client_status: 20, goal_completed: false,
  }));
  const writes: unknown[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ json: body, status });
    if (path === "/api/auth/me") return json(host ? { id: 42, discord_username: "Host", is_admin: false, is_approved: true } : {}, host ? 200 : 401);
    if (path === "/api/features") return json({ generation: false });
    if (path === "/api/deployment") return json({ label: "" });
    if (path.endsWith("/join-room")) {
      if (route.request().method() === "PUT") {
        const changes = route.request().postDataJSON();
        writes.push(changes);
        Object.assign(room, changes);
      }
      return json(room);
    }
    if (path.endsWith("/tracker")) return json({ status: "ok", source: "external", server_status: "external",
      connection_url: connection, players, overall_completion_pct: 20, total_checks_done: 4,
      total_checks_total: 20, goals_completed: 0, goals_total: 2, has_save: true });
    if (path.endsWith("/slots")) return json({ slots: [] });
    if (path.includes("/tracker/slot/")) return json({ error: "Fixture slot details" });
    if (path.endsWith("/activity-stream")) return json({ status: "no_connection", events: [] });
    return json([]);
  });
  return writes;
}

test("join URLs preserve exact slot names and require a verified game and valid address", () => {
  const url = new URL(gameJoinUrl("Pokepelago", slotName, "archipelago.gg:38281")!);
  expect(url.origin).toBe("https://pokepelago.ap-pie.com");
  expect(Object.fromEntries(url.searchParams)).toEqual({ host: "archipelago.gg", port: "38281", name: slotName });
  for (const address of ["", "archipelago.gg", "host:0", "host:65536", "host:1.5", "https://host:123", "host/path:123", "user@host:123"]) {
    expect(gameJoinUrl("Pokepelago", slotName, address)).toBeNull();
  }
  for (const game of ["Crash Team Racing", "toString", "__proto__"]) expect(gameJoinUrl(game, slotName, "host:123")).toBeNull();
  for (const address of ["[2001:db8::1]:38281", "2001:db8::1:38281"]) {
    expect(new URL(gameJoinUrl("Poképelago", slotName, address)!).searchParams.get("host")).toBe("[2001:db8::1]");
  }
});

for (const width of [1440, 390]) {
  test(`slot link joins in a new tab and details remain accessible at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    await mockRoom(page);
    await page.goto("/r/join-room");
    const join = page.getByRole("link", { name: `Join Pokepelago as ${slotName} (opens a new tab)`, exact: true });
    await expect(join).toBeVisible();
    const connectionBar = await page.locator(".tracker-connection").boundingBox();
    const copyButton = await page.locator(".tracker-connection .copy-btn").boundingBox();
    expect(copyButton!.x + copyButton!.width).toBeLessThanOrEqual(connectionBar!.x + connectionBar!.width);
    await expect(join).toHaveAttribute("href", gameJoinUrl("Pokepelago", slotName, "archipelago.gg:38281")!);
    await page.context().route("https://pokepelago.ap-pie.com/**", (route) => route.fulfill({ body: "Game client fixture" }));
    const popupPromise = page.waitForEvent("popup");
    await join.click();
    const popup = await popupPromise;
    await popup.waitForLoadState();
    expect(new URL(popup.url()).searchParams.get("name")).toBe(slotName);
    await popup.close();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("button", { name: `Open detail for ${slotName} (Pokepelago)`, exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Open detail for CTR player (Crash Team Racing)", exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/appie-room-join-${width}.png` });
  });
}

test("missing connection keeps slot details without a broken join link", async ({ page }) => {
  await mockRoom(page, false, "");
  await page.goto("/r/join-room");
  await expect(page.getByRole("button", { name: `Open detail for ${slotName} (Pokepelago)`, exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Join Pokepelago/ })).toHaveCount(0);
});

test("host and port save and clear from Tracker settings, rejecting fractional ports", async ({ page }) => {
  const writes = await mockRoom(page, true);
  await page.goto("/r/join-room");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("tab", { name: "Tracker", exact: true }).click();
  const section = page.locator("section.settings-section").filter({ has: page.getByText("Game server host and port", { exact: true }) });
  await section.getByRole("textbox", { name: "Game server host" }).fill("new.example.com");
  await section.getByRole("spinbutton", { name: "Game server port" }).fill("123.5");
  await section.getByRole("button", { name: "Save", exact: true }).click();
  await expect(section.getByText("Port must be 1-65535")).toBeVisible();
  expect(writes).toHaveLength(0);
  await section.getByRole("spinbutton", { name: "Game server port" }).fill("45678");
  await section.getByRole("button", { name: "Save", exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ external_host: "new.example.com", external_port: 45678 });
  await section.getByRole("button", { name: "Clear", exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[1]).toEqual({ external_host: null, external_port: null });
});
