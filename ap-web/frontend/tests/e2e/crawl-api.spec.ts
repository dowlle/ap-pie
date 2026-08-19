import { expect, test } from "@playwright/test";

const RETIRED_APWORLD = "manual_plantsvszombies2gardendless_trikehard";

test("public catalog excludes every disabled APWorld", async ({ request }) => {
  const response = await request.get("/api/apworlds");
  expect(response.ok()).toBeTruthy();
  const worlds = await response.json() as Array<{ name: string; disabled: boolean }>;
  expect(worlds.some((world) => world.disabled)).toBeFalsy();
  expect(worlds.some((world) => world.name === RETIRED_APWORLD)).toBeFalsy();
});

test("slash-bearing versions reach the real download handler", async ({ request }) => {
  const response = await request.get(
    "/api/apworlds/cobalt_core/release%2F1.1.6/download",
    { maxRedirects: 0 },
  );
  expect(response.status()).toBe(302);
  expect(response.headers().location).toContain("release/1.1.6");
});

test("retired APWorld actions stay truthful", async ({ request }) => {
  const download = await request.get(
    `/api/apworlds/${RETIRED_APWORLD}/0.0.1/download`,
    { maxRedirects: 0 },
  );
  expect(download.status()).toBe(404);

  const builder = await request.get(`/api/apworlds/${RETIRED_APWORLD}/builder-schema`);
  expect(builder.status()).toBe(404);
});

test("unknown API endpoints return an API-shaped 404", async ({ request }) => {
  const response = await request.get("/api/definitely-not-an-endpoint");
  expect(response.status()).toBe(404);
  expect(response.headers()["content-type"]).toContain("application/json");
  await expect(response.json()).resolves.toEqual({ error: "API endpoint not found" });
});
