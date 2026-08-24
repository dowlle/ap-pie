import { expect, test } from "@playwright/test";

const contracts = [
  {
    path: "/",
    title: "Archipelago Pie: Multiworld Randomizer Tools & Guides",
    description: "Learn how Archipelago multiworld randomizers work, build player YAMLs, browse community APWorlds, and organize games with Archipelago Pie.",
    canonical: "https://ap-pie.com/",
    heading: "Your games, connected by one randomizer.",
    type: "WebSite",
  },
  {
    path: "/apworlds",
    title: "APWorld Downloads & YAML Builder | Archipelago Pie",
    description: "Browse community Archipelago APWorlds by game and version, open setup resources, download integrations, and create compatible player YAMLs.",
    canonical: "https://ap-pie.com/apworlds",
    heading: "APWorld downloads and YAML builder",
    type: "CollectionPage",
  },
  {
    path: "/yaml-builder",
    title: "Archipelago YAML Builder | Archipelago Pie",
    description: "Build an Archipelago player YAML from guided game options, review the generated file, and download it for your host or multiworld.",
    canonical: "https://ap-pie.com/yaml-builder",
    heading: "Build an Archipelago player YAML",
    type: "WebApplication",
  },
];

for (const contract of contracts) {
  test(`${contract.path} has deterministic raw search HTML`, async ({ request }) => {
    const response = await request.get(contract.path);
    expect(response.ok()).toBeTruthy();
    const html = await response.text();
    expect(html).toContain(`<title>${contract.title.replaceAll("&", "&amp;")}</title>`);
    expect(html).toContain(`name="description" content="${contract.description}"`);
    expect(html).toContain(`rel="canonical" href="${contract.canonical}"`);
    expect(html).toContain(`<h1>${contract.heading}</h1>`);
    expect(html).toContain(`"@type":"${contract.type}"`);
  });
}

test("rendered public routes keep one visible H1 and their canonical", async ({ page }) => {
  for (const contract of contracts) {
    await page.goto(contract.path);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", contract.canonical);
  }
});

test("public SPA search surfaces appear exactly once in the sitemap", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.ok()).toBeTruthy();
  const xml = await response.text();
  expect(xml.match(/<loc>https:\/\/ap-pie\.com\/apworlds<\/loc>/g)).toHaveLength(1);
  expect(xml.match(/<loc>https:\/\/ap-pie\.com\/yaml-builder<\/loc>/g)).toHaveLength(1);
});

test("CTR screenshots prefer WebP and every fallback stays below 100 KB", async ({ page, request }) => {
  const names = [
    "checks-feed",
    "warp-pad-hub",
    "tutorial-thumb",
    "warp-pad-requirements",
    "custom-resolutions-poster",
    "og-ctr",
  ];
  for (const name of names) {
    for (const extension of ["webp", "jpg"]) {
      const response = await request.get(`/img/ctr/${name}.${extension}`);
      expect(response.ok()).toBeTruthy();
      expect((await response.body()).byteLength).toBeLessThan(100_000);
    }
  }

  await page.goto("/ctr");
  await expect(page.locator('picture source[type="image/webp"]')).toHaveCount(3);
  await expect(page.locator('video[poster$="custom-resolutions-poster.webp"]')).toHaveCount(1);
});
