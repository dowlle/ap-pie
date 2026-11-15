import { expect, test } from "@playwright/test";

const review = {
  status: "fail", reviewed_at: "2026-11-01", method: "source-review",
  summary: "Test fixture: this archive has a failed review.", sha256: "a".repeat(64),
  report_sha256: "b".repeat(64), report_public: false, record_url: "/api/apworlds/security-reviews/test",
};
const fixture = {
  name: "example", display_name: "Example World", detail_slug: "example",
  detail_href: "/apworlds/example", detail_route_kind: "spa", game_name: "Example",
  home: "https://example.com/", tags: [], supported: true, disabled: false,
  is_builtin: false, has_update: false, stability: null, setup_guide: null,
  tracker: null, updated_at: null, editorial: null, review_state: "absent",
  downloadable_versions: [{ version: "2.0" }, { version: "1.0" }],
  builder_versions: [],
  versions: ["2.0", "1.0"].map((version) => ({
    version, url: "https://example.com/world.apworld", local: null, source: "url",
    sha256: "a".repeat(64), security_review: review, fuzz_result: null,
  })),
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/apworlds", (route) => route.fulfill({ json: [fixture] }));
  // Use the SPA shell for this synthetic world without adding a catalog entry
  // to the server. Real server detail routes are covered by the SEO suite.
  await page.route("**/apworlds/example", async (route) => {
    const response = await route.fetch({ url: new URL("/apworlds", route.request().url()).href });
    await route.fulfill({ response });
  });
});

test("failed downloads require a separate acknowledgement for each version", async ({ page }) => {
  // Start at an existing server route, then use the client router for the fixture.
  await page.goto("/apworlds");
  await page.getByRole("link", { name: "Example World", exact: true }).click();
  const versions = page.locator(".apworld-detail-version");
  await expect(versions).toHaveCount(2);
  await expect(page.getByRole("link", { name: /^Download APWorld/ })).toHaveCount(0);
  await versions.first().getByRole("checkbox").check();
  await expect(versions.first().getByRole("link", { name: "Download APWorld 2.0" })).toBeVisible();
  await expect(versions.last().getByRole("link", { name: "Download APWorld 1.0" })).toHaveCount(0);
  await versions.first().getByRole("checkbox").uncheck();
  await expect(page.getByRole("link", { name: /^Download APWorld/ })).toHaveCount(0);
});

test("badges open details, explanations reach the guide and client metadata follows navigation", async ({ page }) => {
  await page.goto("/apworlds");
  await page.getByRole("link", { name: "Review failed", exact: true }).click();
  await expect(page).toHaveURL(/\/apworlds\/example$/);
  await expect(page).toHaveTitle("Example World Archipelago APWorld | Archipelago Pie");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://ap-pie.com/apworlds/example");
  await page.getByRole("button", { name: "Review failed", exact: true }).first().click();
  await expect(page.getByRole("link", { name: "How to read the evidence badges" })).toHaveAttribute("href", "/guides/what-is-the-fuzzer");
  await page.getByRole("link", { name: "Browse all APWorlds" }).click();
  await expect(page).toHaveTitle("APWorld Downloads & YAML Builder | Archipelago Pie");
});

test("unreviewed worlds show missing evidence without editorial or invented actions", async ({ page }) => {
  await page.route("**/api/apworlds", (route) => route.fulfill({ json: [{
    ...fixture, versions: [{ ...fixture.versions[0], security_review: null, sha256: null }],
    downloadable_versions: [], is_builtin: true,
  }] }));
  await page.goto("/apworlds");
  await page.getByRole("link", { name: "Example World", exact: true }).click();
  await expect(page.getByText("Archive SHA-256: Not recorded")).toBeVisible();
  await expect(page.getByRole("button", { name: "Review pending", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tests pending", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Download APWorld|^Build YAML/ })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Editorial review" })).toHaveCount(0);
});
