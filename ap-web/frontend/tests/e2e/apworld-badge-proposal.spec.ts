import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`badge proposal explains evidence and isolates version state at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
      if (path === "/api/features") return route.fulfill({ json: { generation: false } });
      if (path === "/api/deployment") return route.fulfill({ json: { label: "beta" } });
      return route.fulfill({ json: [] });
    });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/style-guide#apworld-badges");
    const section = page.locator("#apworld-badges");
    await expect(section.getByRole("heading", { name: "Every release. Clear evidence." })).toBeVisible({ timeout: 20_000 });
    await section.scrollIntoViewIfNeeded();
    await expect(section.locator(".sg-evidence-card")).toHaveCount(4);
    const pending = section.locator(".sg-evidence-card").filter({ hasText: "Mystery World" });
    await expect(pending.getByRole("button", { name: "Create YAML · 1.1.0" })).toBeEnabled();
    const badge = pending.getByRole("button", { name: "Security: Review pending. Show explanation" });
    await badge.focus();
    await page.keyboard.press("Enter");
    await expect(pending.getByRole("region")).toContainText("has not completed a security review");
    await badge.click();
    await expect(pending.getByRole("region")).toHaveCount(0);
    await pending.getByText("Other versions", { exact: true }).click();
    await pending.getByLabel("Choose version").selectOption("older");
    await expect(pending.getByRole("button", { name: "Create YAML · 1.1.0" })).toBeEnabled();
    await expect(pending.getByRole("button", { name: "Security: Review passed. Show explanation" })).toBeVisible();
    await pending.getByLabel("Choose version").selectOption("latest");
    await expect(pending.getByRole("button", { name: "Create YAML · 1.1.0" })).toBeEnabled();
    const concerns = section.locator(".sg-evidence-card").filter({ hasText: "Action World" });
    await pending.getByText("Other versions", { exact: true }).click();
    await expect(concerns.getByRole("button", { name: "Download" })).toBeEnabled();
    await expect(concerns.getByText("Builder after review", { exact: true })).toBeVisible();
    await expect(concerns.getByRole("button", { name: "Download" })).not.toHaveClass(/btn-primary/);
    const findings = concerns.getByRole("button", { name: "Read findings" });
    await expect(findings).toHaveClass(/btn-primary/);
    await findings.click();
    await expect(concerns.getByRole("region")).toContainText("Review flagged game-launching behavior.");
    await concerns.getByRole("button", { name: "Close explanation" }).click();
    const clean = section.locator(".sg-evidence-card").filter({ hasText: "Racing World" });
    await expect(clean.locator(".sg-evidence-note")).toHaveCount(0);
    await expect(section.locator(".sg-evidence-kind")).toHaveCount(0);
    const warnings = section.locator(".sg-evidence-card").filter({ hasText: "Adventure World" });
    await expect(warnings.getByRole("button", { name: "Create YAML" })).toBeEnabled();
    await expect(section.getByRole("link", { name: "Create Super Metroid YAML" })).toHaveAttribute("href", "/yaml-builder/sm?version=0.6.7");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    await section.scrollIntoViewIfNeeded();
    await section.screenshot({ path: `/tmp/ap-pie-badge-proposal-${width}.png`, style: "nav, .deployment-banner { visibility: hidden !important; }" });
  });
}
