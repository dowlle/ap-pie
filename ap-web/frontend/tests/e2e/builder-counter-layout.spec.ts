import { expect, test } from "@playwright/test";

for (const width of [1440, 820, 390]) {
  test(`long counter labels fit beside editable values at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    await page.route("**/api/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
      if (path === "/api/deployment") return route.fulfill({ json: { label: "" } });
      if (path === "/api/features") return route.fulfill({ json: { generation: false } });
      if (path.includes("builder-schema")) return route.fulfill({ json: {
        game: "Refunct", apworld_name: "refunct", display_name: "Refunct", version: "1.2.2",
        schema: { _format_version: 6, game: "Refunct", ap_version: "", world_version: "1.2.2", categories: ["Minigames"], options: [
          { name: "minigames_likeliness", display_name: "Likeliness of minigames", description: "Choose the likelihood of each minigame.", type: "dict", dict_kind: "counter", category: "Minigames",
            default: { "Block Brawl Minigame": 5, "Funny Bridge Game Minigame": 1, "Climb Narrow Minigame": 1 } },
          { name: "weights", display_name: "Weights", description: "Numeric weight mapping.", type: "dict", dict_kind: "mapping", mapping_value_kind: "number", category: "Minigames",
            default: { long_weight_label_with_multiple_words: 2 } },
        ] },
      } });
      if (path.includes("/presets")) return route.fulfill({ json: { presets: [] } });
      return route.fulfill({ json: [] });
    });
    await page.goto("/yaml-builder/refunct?version=1.2.2");
    await page.getByRole("button", { name: "Start with the game defaults" }).click();
    const rows = page.locator(".yaml-builder-counter-row");
    await expect(rows).toHaveCount(4);
    for (const row of await rows.all()) {
      await row.scrollIntoViewIfNeeded();
      const label = await row.locator("span").boundingBox();
      const input = await row.locator("input").boundingBox();
      expect(label!.width).toBeGreaterThan(80);
      expect(label!.x + label!.width).toBeLessThan(input!.x);
      expect(input!.width).toBeLessThan(110);
    }
    await page.getByRole("spinbutton", { name: "Block Brawl Minigame" }).fill("7");
    await expect(page.getByRole("spinbutton", { name: "Block Brawl Minigame" })).toHaveValue("7");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/appie-counter-layout-${width}.png` });
  });
}
