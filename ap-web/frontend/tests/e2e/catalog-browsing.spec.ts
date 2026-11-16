import { expect, test, type Page } from "@playwright/test";

const worlds = Array.from({ length: 60 }, (_, index) => {
  const builtin = index % 2 === 0;
  const version = { version: index === 1 ? "V1.0.5" : "1.0", source: builtin ? "builtin" : "url", url: null, local: null, sha256: null, fuzz_result: null, security_review: null };
  return {
    name: `world_${index}`, display_name: `World ${String(index).padStart(2, "0")}`,
    game_name: `World ${index}`, detail_href: `/apworlds/world-${index}`, detail_route_kind: "spa",
    tags: [], supported: true, disabled: false, is_builtin: builtin, home: null,
    stability: index < 30 ? "stable" : "beta", setup_guide: index % 3 === 0 ? "/guides/getting-started" : null,
    tracker: index % 5 === 0 ? "https://example.com/tracker" : null, updated_at: "2026-11-15",
    versions: [version], downloadable_versions: builtin ? [] : [version], builder_versions: [],
  };
});

async function mockCatalog(page: Page, signedIn = false) {
  await page.route("**/api/**", route => {
    const path = new URL(route.request().url()).pathname;
    const json = path === "/api/auth/me"
      ? signedIn ? { id: 1, discord_username: "Player", is_admin: false, is_approved: true } : { user: null, auth_enabled: true }
      : path === "/api/features" ? { generation: false, open_room_creation: true }
      : path === "/api/deployment" ? { label: "" }
      : path === "/api/apworlds" ? worlds
      : path === "/api/my/favorite-games" ? { games: ["world_1", "world_31"] } : {};
    return route.fulfill({ json });
  });
}

for (const width of [1440, 390]) {
  test(`pagination, count, search and URL history at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await mockCatalog(page);
    const requests: string[] = [];
    page.on("request", request => requests.push(new URL(request.url()).pathname));
    await page.goto("/apworlds");
    const count = page.locator(".apworlds-count");
    await expect(count).toHaveText("60 APWorlds found · Showing 1 to 24");
    await expect(page.locator(".apworld-catalog-card")).toHaveCount(24);
    const topPages = page.getByRole("navigation", { name: "Catalog pages (top)" });
    await topPages.getByRole("link", { name: "Next" }).click();
    await expect(page).toHaveURL(/page=2/);
    await expect(count).toHaveText("60 APWorlds found · Showing 25 to 48");
    await expect(page.locator(".apworld-catalog-card").first()).toContainText("World 24");
    await page.reload();
    await expect(count).toContainText("Showing 25 to 48");
    await page.getByRole("button", { name: "Built into Archipelago" }).click();
    await expect(page).toHaveURL(/view=builtin/);
    await expect(count).toHaveText("30 APWorlds found · Showing 1 to 24");
    expect(new URL(page.url()).searchParams.has("page")).toBe(false);
    await page.goBack();
    await expect(count).toContainText("60 APWorlds found · Showing 25 to 48");
    await page.goForward();
    await expect(count).toContainText("30 APWorlds found");
    await page.getByRole("searchbox").fill("world_2");
    await expect(count).toHaveText("6 APWorlds found · Showing 1 to 6");
    await expect(page).toHaveURL(/search=world_2/);
    await page.reload();
    await expect(page.getByRole("searchbox")).toHaveValue("world_2");
    await expect(count).toContainText("6 APWorlds found");
    await page.getByRole("searchbox").fill("not-a-real-game");
    await expect(count).toHaveText("0 APWorlds found");
    await expect(page.getByRole("link", { name: "Not listed? Request it" })).toHaveAttribute("href", "/report-issue#request-an-apworld");
    await expect(page.getByText("Try refreshing the index")).toHaveCount(0);
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(count).toContainText("60 APWorlds found");
    expect(requests.filter(path => path === "/api/games")).toHaveLength(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });
}

test("all URL filters restore together, including favorites and sort", async ({ page }) => {
  await mockCatalog(page, true);
  await page.goto("/apworlds?search=World&view=downloadable&stability=beta&favorites=1&sort=name-desc");
  await expect(page.locator(".apworlds-count")).toHaveText("1 APWorld found · Showing 1 to 1");
  await expect(page.locator(".apworld-catalog-card")).toContainText("World 31");
  await expect(page.getByLabel("Sort", { exact: true })).toHaveValue("name-desc");
  await expect(page.getByLabel("Index stability")).toHaveValue("beta");
  await expect(page.getByRole("button", { name: "My favorites" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "My favorites" }).click();
  await expect(page.locator(".apworlds-count")).toContainText("15 APWorlds found");
  await expect(page.locator(".apworld-catalog-card").first()).toContainText("World 59");
});

test("legacy search links, invalid pages, final page and version labels", async ({ page }) => {
  await mockCatalog(page);
  await page.goto("/apworlds?search=world_1&page=999");
  await expect(page.locator(".apworlds-count")).toContainText("11 APWorlds found · Showing 1 to 11");
  await expect(page).not.toHaveURL(/page=/);
  await expect(page.locator(".apworld-card-release").first()).toContainText("V1.0.5 · Latest release");
  await page.goto("/apworlds?page=3");
  await expect(page.locator(".apworld-catalog-card")).toHaveCount(12);
  await expect(page.locator(".apworlds-count")).toContainText("Showing 49 to 60");
  await expect(page.getByRole("link", { name: "Next", exact: true })).toHaveCount(0);
  await page.goto("/apworlds?page=NaN&view=unknown&sort=unknown");
  await expect(page.locator(".apworlds-count")).toContainText("Showing 1 to 24");
  await expect(page.getByLabel("Sort", { exact: true })).toHaveValue("name");
});

test("homepage explains collection and hosting in the first screen", async ({ page }) => {
  await mockCatalog(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const explanation = page.locator(".lp-hero-capability");
  await expect(explanation).toContainText("AP-Pie collects player YAMLs. You generate locally");
  await expect(explanation).toContainText("host on archipelago.gg or your own machine");
  const bounds = await explanation.boundingBox();
  expect(bounds!.y + bounds!.height).toBeLessThan(844);
});

for (const width of [1440, 390]) {
  test(`failed-version downloads stay gated from a later catalog page at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await mockCatalog(page);
    const failed = {
      ...worlds[1], name: "zz_failed", display_name: "ZZ Failed World",
      detail_slug: "zz-failed", detail_href: "/apworlds/zz-failed",
      downloadable_versions: [{ version: "2.0" }, { version: "1.0" }],
      versions: ["2.0", "1.0"].map(version => ({
        ...worlds[1].versions[0], version,
        security_review: { status: "fail", reviewed_at: "2026-11-01", method: "source-review", summary: "Failed archive fixture", sha256: "a".repeat(64), report_sha256: "b".repeat(64), report_public: false, record_url: "/api/apworlds/security-reviews/test" },
      })),
    };
    await page.route("**/api/apworlds", route => route.fulfill({ json: [...worlds, failed] }));
    await page.route("**/apworlds/zz-failed", async route => {
      const response = await route.fetch({ url: new URL("/apworlds", route.request().url()).href });
      await route.fulfill({ response });
    });
    await page.goto("/apworlds?page=3");
    await page.reload();
    const card = page.locator(".apworld-card").filter({ hasText: "ZZ Failed World" });
    const latest = card.getByRole("link", { name: "Download ZZ Failed World v2.0" });
    await expect(latest).toHaveAttribute("href", "/apworlds/zz-failed#version-2.0");
    await expect(latest).not.toHaveAttribute("download");
    await latest.click();
    await expect(page).toHaveURL(/\/apworlds\/zz-failed#version-2.0$/);
    await expect(page.getByRole("link", { name: /^Download APWorld/ })).toHaveCount(0);
    await page.locator('[id="version-2.0"]').getByRole("checkbox").check();
    await expect(page.getByRole("link", { name: "Download APWorld 2.0" })).toHaveAttribute("href", "/api/apworlds/zz_failed/2.0/download");
    await expect(page.getByRole("link", { name: "Download APWorld 1.0" })).toHaveCount(0);
    await page.goBack();
    await expect(page).toHaveURL(/\/apworlds\?page=3$/);
    await card.getByRole("button", { name: /View all 2 versions/ }).click();
    const older = card.getByRole("link", { name: "Download ZZ Failed World v1.0" });
    await expect(older).toHaveAttribute("href", "/apworlds/zz-failed#version-1.0");
    await expect(older).not.toHaveAttribute("download");
    await older.click();
    const version = page.locator('[id="version-1.0"]');
    await expect(page.getByRole("link", { name: /^Download APWorld/ })).toHaveCount(0);
    await version.getByRole("checkbox").check();
    await expect(version.getByRole("link", { name: "Download APWorld 1.0" })).toHaveAttribute("href", "/api/apworlds/zz_failed/1.0/download");
    await expect(page.getByRole("link", { name: "Download APWorld 2.0" })).toHaveCount(0);
  });
}
