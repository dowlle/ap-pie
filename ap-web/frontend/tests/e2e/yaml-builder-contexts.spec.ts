import { expect, test, type Page } from "@playwright/test";

async function ctrSchema(page: Page) {
  const response = await page.request.get("/api/apworlds/ctr/builder-schema?version=0.1.5");
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function mockRoomSchema(page: Page, roomId: string) {
  const schema = await ctrSchema(page);
  await page.route(`**/api/public/rooms/${roomId}/builder-schemas`, (route) =>
    route.fulfill({ json: [schema] }),
  );
}

async function startDefaultsAndReview(page: Page) {
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  await page.getByRole("button", { name: "Review YAML" }).click();
}

async function mockSignedInUser(page: Page) {
  await page.route("**/api/auth/me", (route) => route.fulfill({
    json: {
      id: 42,
      discord_id: "builder-test",
      discord_username: "Builder Test",
      is_admin: false,
      is_approved: true,
      created_at: "2026-08-19T00:00:00Z",
    },
  }));
}

test("standalone builder downloads its finalized YAML", async ({ page }) => {
  await page.goto("/yaml-builder/ctr?version=0.1.5");
  await startDefaultsAndReview(page);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download .yaml" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.yaml$/);
});

test("new builder seeds the player name from Discord once", async ({ page }) => {
  await mockSignedInUser(page);
  await page.goto("/yaml-builder/ctr?version=0.1.5");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  const playerName = page.locator('input[placeholder^="Your slot name"]');
  await expect(playerName).toHaveValue("Builder Test");
  await playerName.fill("EditedByPlayer");
  await page.getByRole("button", { name: "Review YAML" }).click();
  await page.getByRole("button", { name: "Back to options" }).click();
  await expect(playerName).toHaveValue("EditedByPlayer");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/name: EditedByPlayer/);
});

test("builder landing can delete one browser-tab draft", async ({ page }) => {
  const draftKey = "ap-pie:yaml-builder:anonymous:standalone:standalone:pokepelago:0.6.3";
  await page.goto("/yaml-builder");
  await page.evaluate(([key]) => {
    sessionStorage.setItem(key, JSON.stringify({ playerName: "Draft Player" }));
  }, [draftKey]);
  await page.reload();

  await expect(page.getByRole("heading", { name: "Continue your draft" })).toBeVisible();
  await expect(page.getByText("Draft Player · v0.6.3")).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete pokepelago draft" }).click();

  await expect(page.getByText("Draft Player · v0.6.3")).toBeHidden();
  await expect(page.getByRole("heading", { name: "Continue your draft" })).toBeHidden();
  expect(await page.evaluate(([key]) => sessionStorage.getItem(key), [draftKey])).toBeNull();
});

test("anonymous public-room context submits the generated YAML", async ({ page }) => {
  const roomId = "public-builder-test";
  await mockRoomSchema(page, roomId);
  let submitted = "";
  await page.route(`**/api/submit/${roomId}`, async (route) => {
    submitted = (await route.request().postDataJSON()).yaml_content;
    await route.fulfill({
      json: { player_name: "Player1", game: "Crash Team Racing", validation_status: "valid" },
    });
  });
  await page.goto(`/yaml-builder/ctr?context=public-room&room=${roomId}`);
  await startDefaultsAndReview(page);
  await page.getByRole("button", { name: "Submit to this room" }).click();
  await expect(page.getByText(/Submitted Player1/)).toBeVisible();
  expect(submitted).toContain("game: Crash Team Racing");
});

test("host-room context uses the host create endpoint", async ({ page }) => {
  const roomId = "host-builder-test";
  await mockRoomSchema(page, roomId);
  let submitted: Record<string, string> | null = null;
  await page.route(`**/api/rooms/${roomId}/yamls/create`, async (route) => {
    submitted = await route.request().postDataJSON();
    await route.fulfill({
      json: { player_name: "Player1", game: "Crash Team Racing", validation_status: "valid" },
    });
  });
  await page.goto(`/yaml-builder/ctr?context=host-room&room=${roomId}`);
  await startDefaultsAndReview(page);
  await page.getByRole("button", { name: "Add to this room" }).click();
  await expect(page.getByText(/Created Player1/)).toBeVisible();
  expect(submitted?.player_name).toBe("Player1");
  expect(submitted?.yaml_content).toContain("game: Crash Team Racing");
});

test("saved simple YAML reopens its form values and player name", async ({ page }) => {
  await mockSignedInUser(page);
  await page.route("**/api/my/yamls", (route) => route.fulfill({
    json: {
      yamls: [{
        id: 71,
        apworld_name: "ctr",
        version: "0.1.5",
        player_name: "SavedSimple",
        label: "Simple fixture",
        kind: "simple",
        values: { oxide_final_challenge_relic_count: 15 },
        yaml_content: null,
        latest_version: "0.1.5",
        outdated: false,
        warnings: [],
      }],
    },
  }));
  await page.goto("/yaml-builder/ctr?version=0.1.5&from=71");
  await expect(page.locator('input[placeholder^="Your slot name"]')).toHaveValue("SavedSimple");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/oxide_final_challenge_relic_count: 15/);
});

test("saved advanced YAML reopens without dropping custom fields", async ({ page }) => {
  await mockSignedInUser(page);
  const advancedYaml = [
    "name: SavedAdvanced",
    "game: Crash Team Racing",
    "Crash Team Racing:",
    "  goal: oxide",
    "  custom_house_rule: enabled",
    "",
  ].join("\n");
  await page.route("**/api/my/yamls", (route) => route.fulfill({
    json: {
      yamls: [{
        id: 72,
        apworld_name: "ctr",
        version: "0.1.5",
        player_name: "SavedAdvanced",
        label: "Advanced fixture",
        kind: "advanced",
        values: null,
        yaml_content: advancedYaml,
        latest_version: "0.1.5",
        outdated: false,
        warnings: [],
      }],
    },
  }));
  await page.goto("/yaml-builder/ctr?version=0.1.5&from=72");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/name: SavedAdvanced/);
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/custom_house_rule: enabled/);
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Custom values");
});

test("standalone builder can create a room and carry its YAML into it", async ({ page }) => {
  await mockSignedInUser(page);
  await page.route("**/api/templates", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/rooms?status=open", (route) => route.fulfill({ json: [] }));
  let createdRoom = false;
  let attachedYaml = "";
  await page.route("**/api/rooms", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    createdRoom = true;
    await route.fulfill({ json: { id: "created-with-yaml", name: "Builder room" } });
  });
  await page.route("**/api/submit/created-with-yaml", async (route) => {
    attachedYaml = (await route.request().postDataJSON()).yaml_content;
    await route.fulfill({
      json: { player_name: "Player1", game: "Crash Team Racing", validation_status: "valid" },
    });
  });

  await page.goto("/yaml-builder/ctr?version=0.1.5");
  await startDefaultsAndReview(page);
  await page.getByRole("button", { name: "Create room with this YAML" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByPlaceholder("Room name").fill("Builder room");
  await dialog.getByRole("button", { name: "Create", exact: true }).click();
  await expect.poll(() => createdRoom).toBeTruthy();
  await expect.poll(() => attachedYaml).toContain("game: Crash Team Racing");
});
