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
];

for (const contract of contracts) {
  test(`${contract.path} has deterministic raw search HTML`, async ({ request }) => {
    const response = await request.get(contract.path);
    expect(response.ok()).toBeTruthy();
    const html = await response.text();
    expect(html).toContain(`<title>${contract.title}</title>`);
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

test("APWorlds appears exactly once in the sitemap", async ({ request }) => {
  const response = await request.get("/sitemap.xml");
  expect(response.ok()).toBeTruthy();
  const xml = await response.text();
  expect(xml.match(/<loc>https:\/\/ap-pie\.com\/apworlds<\/loc>/g)).toHaveLength(1);
});
