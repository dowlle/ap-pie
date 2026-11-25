import { expect, test } from "@playwright/test";

test.describe("CTR custom tracks without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("searches by author and applies mode and source to the same version", async ({ page }) => {
    await page.goto("/ctr");
    await page.getByRole("link", { name: "Custom tracks", exact: true }).click();
    await expect(page).toHaveTitle("CTR custom tracks | Archipelago Pie");
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://ap-pie.com/ctr/tracks");

    const copper = page.getByRole("link", { name: "Copper Cove", exact: true });
    await expect(copper).toBeVisible();
    await expect(page.getByText("Newest version 1.10.0")).toBeVisible();
    await page.getByText("1 patch slot without a matching track version").click();
    await expect(page.getByText("Slot 8", { exact: true })).toBeVisible();

    await page.getByRole("searchbox", { name: "Title or author" }).fill("TRACKSMITH");
    await page.getByLabel("Game mode").selectOption("arcade");
    await page.getByLabel("Source").selectOption("saphi");
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(page.getByText("No tracks match these filters.")).toBeVisible();

    await page.getByLabel("Source").selectOption("xdelta");
    await page.getByRole("button", { name: "Apply filters" }).click();
    await expect(copper).toBeVisible();
    await expect(page.getByRole("link", { name: "Quartz Quarry" })).toHaveCount(0);
  });

  test("shows credits, modes and publication pages per version at 390 px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ctr/tracks");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("CTR custom tracks");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
    await page.getByRole("link", { name: "Copper Cove" }).click();

    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Copper Cove");
    await expect(page.getByText("Tracksmith (track)")).toBeVisible();
    await expect(page.getByText("Not measured yet")).toBeVisible();
    await expect(page.getByText("Race against AI", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Project Saphi", exact: true })).toHaveAttribute("href", "https://www.projectsaphi.com/tracks/121");
    await expect(page.getByText("CopperPack.xdelta · Slot 7")).toBeVisible();
    await expect(page.getByText("CopperPack.xdelta · Slot 9")).toBeVisible();
    await expect(page.getByRole("link", { name: "Patch release page" }).first()).toHaveAttribute("href", "https://example.org/copper-pack/");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  });
});

test("links the CTR Builder to the track list", async ({ page }) => {
  await page.goto("/yaml-builder/ctr?version=0.1.5");
  const tracks = page.getByRole("link", { name: "Custom tracks", exact: true });
  await expect(tracks).toHaveAttribute("href", "/ctr/tracks");
  await tracks.click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("CTR custom tracks");
});
