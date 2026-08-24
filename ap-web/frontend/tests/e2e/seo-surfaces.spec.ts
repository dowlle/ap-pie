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
    expect(html).toContain('"@id":"https://ap-pie.com/#organization"');
    expect(html).toContain('"@id":"https://ap-pie.com/#website"');
  });
}

test("server-rendered pages expose linked, page-appropriate JSON-LD", async ({ request }) => {
  const cases = [
    { path: "/guides", types: ["CollectionPage", "ItemList"], absent: "TechArticle" },
    { path: "/guides/getting-started", types: ["WebPage", "TechArticle", "BreadcrumbList"], absent: "SoftwareApplication" },
    { path: "/privacy", types: ["WebPage", "BreadcrumbList"], absent: "TechArticle" },
    { path: "/ctr", types: ["WebPage", "SoftwareApplication", "BreadcrumbList"], absent: "TechArticle" },
    { path: "/ctr/download", types: ["WebPage", "SoftwareApplication", "BreadcrumbList"], absent: "TechArticle" },
  ];

  for (const entry of cases) {
    const response = await request.get(entry.path);
    expect(response.ok()).toBeTruthy();
    const html = await response.text();
    const match = html.match(/<script type="application\/ld\+json">([^<]+)<\/script>/);
    expect(match, `${entry.path} should contain JSON-LD`).not.toBeNull();
    const data = JSON.parse(match![1]);
    expect(data["@context"]).toBe("https://schema.org");
    expect(data["@graph"]).toEqual(expect.arrayContaining([
      expect.objectContaining({ "@id": "https://ap-pie.com/#organization", "@type": "Organization" }),
      expect.objectContaining({ "@id": "https://ap-pie.com/#website", "@type": "WebSite" }),
    ]));
    const types = data["@graph"].flatMap((node: { "@type": string | string[] }) => node["@type"]);
    for (const type of entry.types) expect(types).toContain(type);
    expect(types).not.toContain(entry.absent);
  }
});

test("guide collection lists every published guide exactly once", async ({ request }) => {
  const response = await request.get("/guides");
  const html = await response.text();
  const data = JSON.parse(html.match(/<script type="application\/ld\+json">([^<]+)<\/script>/)![1]);
  const itemList = data["@graph"].find((node: { "@type": string }) => node["@type"] === "ItemList");
  expect(itemList.numberOfItems).toBe(itemList.itemListElement.length);
  expect(new Set(itemList.itemListElement.map((item: { url: string }) => item.url)).size).toBe(itemList.numberOfItems);
});

test("CTR software data stays aligned with the visible stable release", async ({ request }) => {
  const response = await request.get("/ctr/download");
  const html = await response.text();
  const data = JSON.parse(html.match(/<script type="application\/ld\+json">([^<]+)<\/script>/)![1]);
  const software = data["@graph"].find((node: { "@type": string }) => node["@type"] === "SoftwareApplication");
  expect(html).toContain(`latest stable release is <strong>${software.softwareVersion}</strong>`);
  expect(software.downloadUrl).toEqual([
    "https://ap-pie.com/ctr/download/windows",
    "https://ap-pie.com/ctr/download/linux",
  ]);
});

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
