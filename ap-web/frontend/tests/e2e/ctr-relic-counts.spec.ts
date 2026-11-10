import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { load } from "js-yaml";

async function openCtr(page: import("@playwright/test").Page, apworld = "ctr", game = "Crash Team Racing") {
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
    if (path === "/api/deployment") return route.fulfill({ json: { label: "" } });
    if (path === "/api/features") return route.fulfill({ json: { generation: false } });
    if (path.includes("builder-schema")) return route.fulfill({ json: {
      game, apworld_name: apworld, display_name: game, version: "0.3.0",
      schema: { _format_version: 6, game, ap_version: "", world_version: "0.3.0", categories: ["Items"], options: [
        { name: "item_pool", display_name: "Item Pool", description: "Which items exist in the seed.", type: "dict", category: "Items", default: {} },
      ] },
    } });
    if (path.includes("/presets")) return route.fulfill({ json: { presets: [] } });
    return route.fulfill({ json: [] });
  });
  await page.goto(`/yaml-builder/${apworld}?version=0.3.0`);
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  await page.getByText("Items (1)").click();
}

async function downloadYaml(page: import("@playwright/test").Page) {
  await page.getByRole("button", { name: "Review YAML" }).click();
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download .yaml" }).click();
  const downloaded = await pending;
  return load(await readFile((await downloaded.path())!, "utf8")) as Record<string, Record<string, unknown>>;
}

test("CTR item_pool shows relic number fields that write base relics", async ({ page }) => {
  await openCtr(page);
  const sapphire = page.getByRole("spinbutton", { name: "Sapphire Relics" });
  const gold = page.getByRole("spinbutton", { name: "Gold Relics" });
  const platinum = page.getByRole("spinbutton", { name: "Platinum Relics" });
  await expect(sapphire).toHaveValue("18");
  await expect(gold).toHaveValue("18");
  await expect(platinum).toHaveValue("0");
  await platinum.fill("6");
  // The free-text box stays and shows the same value.
  await expect(page.getByRole("textbox", { name: "Item Pool" })).toHaveValue(/platinum: 6/);
  const yaml = await downloadYaml(page);
  expect(yaml["Crash Team Racing"].item_pool).toEqual({ base: { relics: { sapphire: 18, gold: 18, platinum: 6 } } });
});

test("typing other item_pool entries keeps them when a relic field changes", async ({ page }) => {
  await openCtr(page);
  const box = page.getByRole("textbox", { name: "Item Pool" });
  await box.fill("extra:\n  relics:\n    gold: 2\nbase:\n  tokens:\n    red: 4");
  await page.getByRole("spinbutton", { name: "Platinum Relics" }).fill("3");
  await expect(box).toHaveValue(/tokens:/);
  const yaml = await downloadYaml(page);
  expect(yaml["Crash Team Racing"].item_pool).toEqual({
    extra: { relics: { gold: 2 } },
    base: { tokens: { red: 4 }, relics: { sapphire: 18, gold: 18, platinum: 3 } },
  });
});

test("other games keep the plain item_pool box", async ({ page }) => {
  await openCtr(page, "otherworld", "Other World");
  await expect(page.getByRole("textbox", { name: "Item Pool" })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "Platinum Relics" })).toHaveCount(0);
});
