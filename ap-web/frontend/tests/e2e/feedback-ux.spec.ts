import { expect, test, type Page, type Route } from "@playwright/test";

const user = {
  id: 42,
  discord_id: "discord-42",
  discord_username: "Appie",
  is_admin: false,
  is_approved: true,
  is_owner: false,
  room_creation_blocked: false,
  created_at: "2026-09-01T08:00:00+00:00",
};

const room = {
  id: "feedback-room",
  name: "September Async",
  description: "",
  host_name: "Appie",
  host_user_id: 42,
  status: "closed",
  seed: null,
  generation_log: null,
  spoiler_level: 0,
  race_mode: false,
  max_players: 0,
  max_yamls_per_user: 0,
  external_host: null,
  external_port: null,
  require_discord_login: false,
  submit_deadline: null,
  tracker_url: null,
  tracker_slot_name: null,
  claim_mode: false,
  allow_mixed_apworld_versions: false,
  force_latest_apworld_versions: false,
  auto_upgrade_apworld_pins: true,
  yamls: [{
    id: 7,
    player_name: "AppieCTR",
    game: "Crash Team Racing",
    filename: "AppieCTR.yaml",
    validation_status: "validated",
    validation_error: null,
    submitter_username: "Appie",
    submitter_user_id: 42,
    apworld_versions: {},
  }],
};

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockHostRoom(page: Page, status: "open" | "closed" = "closed") {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") return json(route, user);
    if (url.pathname === "/api/features") return json(route, { generation: false, open_room_creation: true });
    if (url.pathname === "/api/deployment") return json(route, { label: "beta" });
    if (url.pathname === "/api/public/rooms/feedback-room") {
      return json(route, {
        ...room,
        status,
        viewer_capabilities: { can_manage_room: true, can_submit: false, can_coordinate: true },
        player_count: 1,
      });
    }
    if (url.pathname === "/api/rooms/feedback-room") return json(route, { ...room, status });
    if (url.pathname.endsWith("/builder-schemas")) return json(route, [{
      game: "Crash Team Racing",
      apworld_name: "ctr",
      display_name: "Crash Team Racing",
      version: "0.2.0-alpha6",
      pending: false,
      schema: {
        _format_version: 4,
        game: "Crash Team Racing",
        ap_version: "0.6.7",
        world_version: "0.2.0-alpha6",
        categories: [],
        options: [],
      },
    }]);
    if (url.pathname === "/api/apworlds") return json(route, [{
      name: "ctr",
      display_name: "Crash Team Racing",
      game_name: "Crash Team Racing",
      home: "",
      tags: [],
      supported: true,
      disabled: false,
      is_builtin: false,
      has_update: false,
      versions: [],
      downloadable_versions: [{ version: "0.2.0-alpha6" }],
      stability: "alpha",
      setup_guide: null,
      tracker: null,
      updated_at: "2026-09-01",
      editorial: null,
      review_state: "absent",
    }]);
    if (url.pathname.endsWith("/apworlds")) return json(route, [{
      game: "Crash Team Racing",
      yaml_count: 1,
      in_index: true,
      apworld_name: "ctr",
      display_name: "Crash Team Racing",
      home: "https://example.com/source",
      tags: [],
      selected_version: "0.2.0-alpha6",
      download_url: "/downloads/ctr.apworld",
      available_versions: [{
        version: "0.2.0-alpha6", source: "url", sha256: "abc", url: "/downloads/ctr.apworld", fuzz_result: null,
      }],
      policy: "required",
      auto_latest: false,
      stability: "alpha",
      setup_guide: "/guides/ctr",
      tracker: null,
      updated_at: "2026-09-01",
    }]);
    return json(route, { error: "not mocked" }, 404);
  });
}

test("canonical host room keeps private controls on the shareable route", async ({ page }) => {
  await mockHostRoom(page);
  await page.goto("/rooms/feedback-room");
  await expect(page).toHaveURL(/\/r\/feedback-room$/);
  await expect(page.getByRole("heading", { level: 1, name: "September Async" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable tracker" })).toBeVisible();
  await expect(page.getByText("You", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Enable tracker" }).click();
  await expect(page.getByRole("tab", { name: "Tracker" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Add this room's archipelago.gg tracker URL", { exact: false })).toBeVisible();
});

test("one role-aware header omits Market and keeps public orientation links", async ({ page }) => {
  await mockHostRoom(page);
  await page.goto("/r/feedback-room");
  const navigation = page.getByRole("navigation", { name: "Main navigation" });
  await expect(navigation.getByRole("link", { name: "APWorlds" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "YAML Builder" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Guides" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Rooms" })).toBeVisible();
  await expect(navigation.getByRole("link", { name: "Market" })).toHaveCount(0);
});

test("generic room Create YAML opens the game picker and preserves room context", async ({ page }) => {
  await mockHostRoom(page, "open");
  await page.goto("/r/feedback-room");
  await page.getByRole("button", { name: "Create YAML" }).click();
  await expect(page).toHaveURL(/\/yaml-builder\?context=host-room&room=feedback-room$/);
  await expect(page.getByRole("heading", { level: 1, name: "Build a player YAML" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Crash Team Racing/ })).toBeVisible();
});

test("room APWorld action says Download and retains Setup guide", async ({ page }) => {
  await mockHostRoom(page);
  await page.goto("/r/feedback-room");
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("tab", { name: "APWorlds" }).click();
  const settings = page.locator("dialog.settings-modal");
  await expect(settings.getByRole("link", { name: "Download", exact: true })).toHaveAttribute("download", "");
  await expect(settings.getByRole("link", { name: "Setup guide" })).toHaveAttribute("href", "/guides/ctr");
  await expect(settings.getByRole("link", { name: "Preview", exact: true })).toHaveCount(0);
});

test("shared room search and navigation remain usable on a phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockHostRoom(page);
  await page.goto("/r/feedback-room");
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.getByRole("navigation", { name: "Main navigation" }).getByRole("link", { name: "YAML Builder" })).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search submitted YAMLs" });
  await expect(search).toBeVisible();
  await search.fill("CTR");
  await expect(page.getByText("1 of 1")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
