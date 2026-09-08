import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { load } from "js-yaml";

const user = { id: 42, discord_username: "Player", is_admin: false, is_approved: false, is_owner: false };
const world = { name: "fixture", display_name: "Fixture Game", game_name: "Fixture Game", disabled: false,
  is_builtin: false, stability: "stable", home: "", tags: [], downloadable_versions: [{ version: "1.0.0" }],
  versions: [{ version: "1.0.0", source: "url", url: "https://example.com/fixture.apworld" }] };
const room = { id: "shared", name: "Shared Room", status: "open", submit_deadline: null,
  host_name: "Host", host_user_id: 99, require_discord_login: true, yamls: [], player_count: 0,
  max_players: 0, max_yamls_per_user: 0, viewer_capabilities: { can_manage_room: false, can_submit: true } };

async function mockApp(page: Page, signedIn = true) {
  const state = { favorites: [] as string[], joined: false, submitted: "", refuse: false };
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({ json: body, status });
    if (path === "/api/auth/me") return json(signedIn ? user : { error: "Sign in" }, signedIn ? 200 : 401);
    if (path === "/api/features") return json({ generation: false, open_room_creation: true });
    if (path === "/api/deployment") return json({ label: "" });
    if (path === "/api/apworlds") return json([world]);
    if (path === "/api/my/favorite-games/fixture") {
      if (state.refuse) return json({ error: "Could not save favorite" }, 503);
      state.favorites = method === "PUT" ? ["fixture"] : [];
    }
    if (path.startsWith("/api/my/favorite-games")) return json({ games: state.favorites });
    if (path === "/api/my/rooms/shared") state.joined = method === "PUT";
    if (path.startsWith("/api/my/rooms")) return json({ rooms: state.joined ? [{ ...room, joined: true, is_host: false }] : [] });
    if (path === "/api/public/rooms/shared") return json(room);
    if (path.startsWith("/api/public/rooms/")) return json([]);
    if (path === "/api/apworlds/fixture/builder-schema") return json({ apworld_name: "fixture", game: "Fixture Game", display_name: "Fixture Game", version: "1.0.0",
      schema: { _format_version: 6, game: "Fixture Game", ap_version: "", world_version: "", categories: [], options: [] } });
    if (path.startsWith("/api/presets")) return json({ presets: [] });
    if (path === "/api/submit/shared") {
      state.submitted = route.request().postDataJSON().yaml_content;
      return json({ player_name: "Player", game: "Fixture Game", validation_status: "validated" });
    }
    if (path === "/api/my/yamls") return json({ yamls: [] });
    if (path === "/api/my/submissions") return json({ submissions: [] });
    if (path === "/api/events") return json({ ok: true });
    return json({ error: "Not mocked" }, 404);
  });
  return state;
}

test("favorites survive reload and can be removed from My stuff", async ({ page }) => {
  const state = await mockApp(page);
  await page.goto("/apworlds");
  await page.getByRole("button", { name: "Add Fixture Game to favorite games" }).click();
  expect(state.favorites).toEqual(["fixture"]);
  await page.reload();
  await expect(page.getByRole("button", { name: "Remove Fixture Game from favorite games" })).toHaveAttribute("aria-pressed", "true");
  await page.goto("/my/favorites");
  await expect(page.getByRole("link", { name: "Create YAML" }).last()).toHaveAttribute("href", "/yaml-builder/fixture?version=1.0.0");
  await page.getByRole("button", { name: "Remove Fixture Game from favorite games" }).click();
  await expect(page.getByText(/No favorite games yet/)).toBeVisible();
});

test("failed favorite writes keep the previous state", async ({ page }) => {
  const state = await mockApp(page);
  state.refuse = true;
  await page.goto("/apworlds");
  await page.getByRole("button", { name: "Add Fixture Game to favorite games" }).click();
  await expect(page.getByRole("alert")).toContainText("Could not save favorite");
  await expect(page.getByRole("button", { name: "Add Fixture Game to favorite games" })).toHaveAttribute("aria-pressed", "false");
});

test("join an empty room, then send a builder YAML to it", async ({ page }) => {
  const state = await mockApp(page);
  await page.goto("/r/shared");
  await page.getByRole("button", { name: "Join room", exact: true }).click();
  await expect(page.getByText("Joined. You can select this room in the YAML builder.")).toBeVisible();
  expect(state.submitted).toBe("");
  await page.goto("/yaml-builder/fixture?version=1.0.0");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  await page.getByRole("button", { name: "Review YAML" }).click();
  await page.getByRole("combobox", { name: "Room to send YAML to" }).selectOption("shared");
  await page.getByRole("button", { name: "Add to room", exact: true }).click();
  await expect(page.getByRole("link", { name: "Open the room" })).toHaveAttribute("href", "/r/shared");
  expect(state.submitted).toContain("game: Fixture Game");
  await page.goto("/my/rooms");
  await page.getByRole("button", { name: "Leave room" }).click();
  await expect(page.getByText("You haven't joined any rooms yet.")).toBeVisible();
});

test("anonymous catalog has no favorite writes and exposes the support link", async ({ page }) => {
  await mockApp(page, false);
  await page.goto("/apworlds");
  await expect(page.getByRole("heading", { name: "Fixture Game" })).toBeVisible();
  await expect(page.getByRole("button", { name: /favorite games/ })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Support Dowlle on Ko-fi" })).toHaveAttribute("href", "https://ko-fi.com/dowlle");
});

test("favorites fit a narrow screen", async ({ page }) => {
  const state = await mockApp(page); state.favorites = ["fixture"];
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/my/favorites");
  await expect(page.getByRole("button", { name: "Remove Fixture Game from favorite games" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("real archived schema exports its exact game identity and options", async ({ page }) => {
  test.skip(!process.env.BUILDER_REAL_SCHEMA, "Set BUILDER_REAL_SCHEMA to a locally audited schema JSON");
  const schema = JSON.parse(await readFile(process.env.BUILDER_REAL_SCHEMA!, "utf8"));
  await mockApp(page);
  await page.route("**/api/apworlds/fixture/builder-schema?*", (route) => route.fulfill({ json: {
    apworld_name: "fixture", game: schema.game, display_name: schema.game, version: "1.4.4", schema,
  } }));
  await page.goto("/yaml-builder/fixture?version=1.4.4");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  await page.getByRole("button", { name: "Review YAML" }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download .yaml" }).click();
  const download = await downloadPromise;
  const doc = load(await readFile((await download.path())!, "utf8")) as Record<string, unknown>;
  expect(doc.game).toBe(schema.game);
  const values = doc[schema.game] as Record<string, unknown>;
  for (const option of schema.options) expect(values).toHaveProperty(option.name);
});
