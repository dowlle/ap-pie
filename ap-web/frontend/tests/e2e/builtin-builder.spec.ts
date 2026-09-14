import { expect, test } from "@playwright/test";
import { load } from "js-yaml";
import { readFileSync } from "node:fs";

const records = JSON.parse(readFileSync(new URL("../../../builtin_schemas/catalog.json", import.meta.url), "utf8")).worlds;
test.use({ extraHTTPHeaders: { DNT: "1" } });

for (const name of ["sm", "alttp"]) {
  test(`built-in ${name} exports the official release defaults`, async ({ page, baseURL }) => {
    const record = records[name];
    if (baseURL?.includes("127.0.0.1")) {
      await page.route("**/api/**", async (route) => {
        const path = new URL(route.request().url()).pathname;
        if (path === "/api/auth/me") return route.fulfill({ status: 401, json: {} });
        if (path === "/api/features") return route.fulfill({ json: { generation: false } });
        if (path === "/api/deployment") return route.fulfill({ json: { label: "beta" } });
        if (path.endsWith("/presets")) return route.fulfill({ json: { presets: [] } });
        if (path === `/api/apworlds/${name}/builder-schema`) return route.fulfill({ json: { game: record.game, display_name: record.game, apworld_name: name, version: record.version, schema: record.schema } });
        return route.fulfill({ json: [] });
      });
    }
    await page.goto(`/yaml-builder/${name}?version=0.6.7`);
    await page.getByRole("button", { name: "Start with the game defaults" }).click();
    await page.getByLabel("Player name", { exact: true }).fill("BuiltinTest");
    await page.getByRole("button", { name: /^Review YAML/ }).click();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download .yaml", exact: true }).click();
    const file = await download;
    const path = `/tmp/ap-pie-builtin-${name}.yaml`;
    await file.saveAs(path);
    const document = load(readFileSync(path, "utf8")) as { name: string; game: string; requires: { version: string; game?: unknown }; [key: string]: unknown };
    expect(document.name).toBe("BuiltinTest");
    expect(document.game).toBe(record.game);
    expect(document.requires.version).toBe("0.6.7");
    expect(document.requires.game).toBeUndefined();
    const options = document[record.game] as Record<string, unknown>;
    for (const option of record.schema.options) expect(options[option.name]).toEqual(option.default);
    await page.screenshot({ path: `/tmp/ap-pie-builtin-${name}-builder.png`, fullPage: true });
  });
}
