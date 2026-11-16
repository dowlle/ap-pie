import { expect, test } from "@playwright/test";

for (const width of [1440, 390]) {
  test(`registry reads and anonymous write protection at ${width}px`, async ({ page }) => {
    const features = await (await page.request.get("/api/features")).json();
    test.skip(!features.ctr_registry, "Registry is enabled only on beta.");
    const listing = await page.request.get("/api/ctr/tracks");
    expect(listing.status()).toBe(200);
    const { tracks } = await listing.json();
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/custom-tracks");
    await expect(page.getByRole("heading", { name: "CTR custom tracks", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in with Discord to submit" })).toBeVisible();
    if (tracks.length) {
      await expect(page.getByText(tracks[0].display_title, { exact: true })).toBeVisible();
    } else {
      await expect(page.getByText("No reviewed tracks yet.")).toBeVisible();
    }
    const submit = await page.request.post("/api/ctr/tracks/submissions", {
      data: { kind: "new_track", title: "Unauthorized fixture" },
    });
    expect(submit.status()).toBe(401);
    expect((await page.request.get("/api/admin/ctr/tracks")).status()).toBe(401);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });
}
