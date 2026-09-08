import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
    if (path === "/api/features") return route.fulfill({ json: { generation: false } });
    if (path === "/api/deployment") return route.fulfill({ json: { label: "" } });
    if (path === "/api/apworlds") return route.fulfill({ json: ["clean", "flaky", "broken", null].map((verdict, i) => ({
      name: `fixture${i}`, display_name: `Fixture ${i}`, disabled: false, is_builtin: false, tags: [],
      downloadable_versions: [{ version: "1.2.3" }],
      versions: [{ version: "1.2.3", source: "url", url: "https://example.com/world.apworld", fuzz_result: verdict && {
        verdict, default_rate: 0.004, worst_hook: "check-determinism", worst_hook_rate: 0.75, seeds: 5000, fuzzed_at: "2026-09-08",
      } }],
    })) });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/apworlds");
});

for (const verdict of ["clean", "flaky", "broken"]) {
  test(`${verdict} badge opens version detail by keyboard and restores focus`, async ({ page }) => {
    const badge = page.getByRole("button", { name: new RegExp(`v1.2.3: ${verdict}`) });
    await badge.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "What is the fuzzer?" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: `Version 1.2.3: ${verdict}` })).toBeVisible();
    await expect(dialog.getByText("0.40%", { exact: true })).toBeVisible();
    await expect(dialog.getByText("75.00%", { exact: false })).toBeVisible();
    await expect(dialog.getByRole("link", { name: "Read the full fuzzer guide" })).toHaveAttribute("href", "/guides/what-is-the-fuzzer");
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(badge).toBeFocused();
  });
}

test("missing data is silent and mobile modal stays usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await expect(page.getByRole("button", { name: /What is the fuzzer/ })).toHaveCount(3);
  await page.getByRole("button", { name: /v1.2.3: broken/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
  await page.screenshot({ path: "/tmp/appie-fuzzer-modal-mobile.png" });
  await dialog.getByRole("button", { name: "Got it" }).click();
  await expect(dialog).toHaveCount(0);
});
