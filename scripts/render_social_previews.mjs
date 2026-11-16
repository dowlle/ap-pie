// Render the existing guide artwork as PNG for social clients that reject SVG.
// Run after npm ci in ap-web/frontend.
import { chromium } from "../ap-web/frontend/node_modules/@playwright/test/index.mjs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const directory = new URL("../ap-web/frontend/public/img/guides/", import.meta.url);
const source = await readFile(new URL("og-guides.svg", directory), "utf8");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  for (const [name, svg] of [
    ["og-guides.png", source],
    ["og-tools.png", source.replace("Archipelago Pie guides", "Archipelago Pie tools")
      .replace(">Guides</text>", ">Multiworld tools</text>")
      .replace('font-size="100"', 'font-size="68"')
      .replace("From first setup to connected and playing.", "APWorlds, player YAMLs and setup guides.")
      .replace('font-size="34"', 'font-size="28"')],
  ]) {
    await page.setContent('<style>body{margin:0}</style>' + svg);
    await page.screenshot({ path: fileURLToPath(new URL(name, directory)) });
  }
} finally {
  await browser.close();
}
