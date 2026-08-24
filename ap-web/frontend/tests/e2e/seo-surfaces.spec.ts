import { expect, test } from "@playwright/test";

const contracts = [
  {
    path: "/",
    title: "Archipelago Multiworld Tools & Guides | Archipelago Pie",
    description: "Build player YAMLs, browse community APWorlds, and learn how to join, host, and play Archipelago multiworld randomizers.",
    canonical: "https://ap-pie.com/",
    heading: "Your games, connected by one randomizer.",
    type: "WebSite",
  },
  {
    path: "/apworlds",
    title: "APWorld Downloads & YAML Builder | Archipelago Pie",
    description: "Browse APWorld downloads by game and version, find setup guides, and build compatible player YAMLs for Archipelago multiworlds.",
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

test("all sitemap metadata fits the Stef Appelhof SERP simulator", async ({ page, request }) => {
  // Contract from https://stefappelhof.com/seo-tools/serp-simulator/:
  // Arial 20px titles under 600px; Arial 14px descriptions under 960px.
  const sitemap = await (await request.get("/sitemap.xml")).text();
  const paths = [...sitemap.matchAll(/<loc>https:\/\/ap-pie\.com([^<]*)<\/loc>/g)]
    .map((match) => match[1] || "/");
  const titles = new Set<string>();
  const descriptions = new Set<string>();

  for (const path of paths) {
    const response = await request.get(path);
    expect(response.ok(), `${path} should be available`).toBeTruthy();
    const metadata = await page.evaluate((html) => {
      const document = new DOMParser().parseFromString(html, "text/html");
      const title = document.title.trim();
      const description = document.querySelector('meta[name="description"]')?.getAttribute("content")?.trim() || "";
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d")!;
      context.font = "20px Arial";
      const titlePixels = Math.round(context.measureText(title).width);
      context.font = "14px Arial";
      const descriptionPixels = Math.round(context.measureText(description).width);
      return { title, description, titlePixels, descriptionPixels };
    }, await response.text());

    expect(metadata.title, `${path} needs a title`).not.toBe("");
    expect(metadata.description, `${path} needs a description`).not.toBe("");
    expect(metadata.titlePixels, `${path} title: ${metadata.title}`).toBeLessThan(600);
    expect(metadata.descriptionPixels, `${path} description: ${metadata.description}`).toBeLessThan(960);
    expect(titles.has(metadata.title), `${path} title must be unique`).toBeFalsy();
    expect(descriptions.has(metadata.description), `${path} description must be unique`).toBeFalsy();
    titles.add(metadata.title);
    descriptions.add(metadata.description);
  }
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
