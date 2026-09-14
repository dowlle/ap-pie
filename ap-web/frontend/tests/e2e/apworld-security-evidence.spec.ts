import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`review dispositions and Actions links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const statuses = ["pass", "needs_review", "fail", "held", "human_accepted", null];
    const labels = ["Review passed", "Review concerns", "Review failed", "Review held", "Concerns accepted", "Review pending"];
    const run = "https://github.com/dowlle/Archipelago-index/actions/runs/34729973615";
    const saved = "https://github.com/dowlle/Archipelago-index/blob/" + "a".repeat(40) + "/index/fixture.toml";
    const result = { verdict: "broken", default_rate: 0, worst_hook: "check-item-location-count", worst_hook_rate: 1, seeds: 5000, fuzzed_at: "2026-09-13", report_url: run, record_url: saved };
    const worlds = statuses.map((status, i) => ({
      name: `review${i}`, display_name: `Review fixture ${i}`, game_name: `Review fixture ${i}`, disabled: false, is_builtin: false, tags: [],
      downloadable_versions: [{ version: "2.0" }], builder_versions: [{ version: "2.0" }],
      versions: [{ version: "2.0", source: "url", sha256: "a".repeat(64), url: "https://example.com/world.apworld", fuzz_result: result,
        security_review: status && { status, reviewed_at: "2026-09-09T12:00:00Z", method: "automated-source-review", summary: `Exact-byte outcome: ${status}`, rationale: status === "needs_review" ? "The review flagged an unchecked extraction path. Human assessment is still required." : undefined, sha256: "a".repeat(64), report_sha256: "b".repeat(64), report_public: false, record_url: "/api/apworlds/security-reviews/" + "c".repeat(64) } }],
    }));
    await page.route("**/api/**", route => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
      if (path === "/api/features") return route.fulfill({ json: { generation: false } });
      if (path === "/api/deployment") return route.fulfill({ json: { label: "beta" } });
      if (path === "/api/apworlds") return route.fulfill({ json: [...worlds, { ...worlds[5], name: "builtin", display_name: "Built-in fixture", is_builtin: true, versions: [], downloadable_versions: [], builder_versions: [{ version: "0.6.7" }] }] });
      return route.fulfill({ json: [] });
    });
    const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
    await page.goto("/apworlds");
    for (let i = 0; i < statuses.length; i++) {
      const card = page.locator(".apworld-catalog-card").filter({ hasText: `Review fixture ${i}` });
      const badge = card.getByRole("button", { name: labels[i], exact: true });
      await badge.scrollIntoViewIfNeeded();
      if (statuses[i] === "fail") {
        await card.getByRole("button", { name: "Read review", exact: true }).click();
      } else {
        await badge.focus(); await page.keyboard.press("Enter");
      }
      const detail = card.getByRole("region", { name: "Security review explanation" });
      await expect(detail).toBeVisible();
      if (statuses[i]) {
        if (statuses[i] === "needs_review") {
          await expect(detail).toContainText("The review flagged an unchecked extraction path. Human assessment is still required.");
          await expect(detail).toContainText("Exact-byte outcome: needs_review");
        }
        await expect(detail).toContainText("a".repeat(64));
        await expect(detail).toContainText("full source report is private");
        await expect(detail.getByRole("link", { name: "Public review record" })).toHaveAttribute("href", "/api/apworlds/security-reviews/" + "c".repeat(64));
      } else {
        await expect(detail).toContainText("No matching security review");
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await detail.getByRole("button", { name: "Close explanation" }).click();
      await expect(card.getByRole("link", { name: `Download Review fixture ${i} v2.0` })).toBeVisible();
    }
    const builtin = page.locator(".apworld-catalog-card").filter({ hasText: "Built-in fixture" });
    await expect(builtin.getByRole("button", { name: "Review not applicable", exact: true })).toBeVisible();
    const card = page.locator(".apworld-catalog-card").filter({ hasText: "Review fixture 2" });
    await card.getByRole("button", { name: "Generation warnings", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("link", { name: "View test run" })).toHaveAttribute("href", run);
    await expect(dialog.getByRole("link", { name: "View recorded result on GitHub" })).toHaveAttribute("href", saved);
    await expect(dialog).toContainText("100.00%");
    await page.keyboard.press("Escape"); await expect(dialog).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
