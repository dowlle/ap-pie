import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

async function fixtures(page: Page, signedIn = true) {
  let signed = signedIn;
  const writes: { method: string; path: string; body: Record<string, unknown> }[] = [];
  const events: string[] = [];
  const user = { id: 424242, discord_username: "JourneyTest", is_admin: false, is_approved: true };
  const saved = { id: 71, apworld_name: "ctr", version: "0.2.0-alpha7", player_name: "ExistingSetup", label: "Weekend setup", kind: "simple", values: { racer_locked_pads: 7 }, latest_version: "0.2.0-alpha7", outdated: false, warnings: [] };
  await page.route("**/api/**", async route => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    if (path === "/api/auth/login") { signed = true; return route.fulfill({ status: 302, headers: { location: url.searchParams.get("next") || "/" } }); }
    if (path === "/api/auth/me") return route.fulfill({ status: signed ? 200 : 401, json: signed ? user : { error: "Not logged in" } });
    if (path === '/api/features') return route.fulfill({ json: { generation: false, open_room_creation: true } });
    if (path === '/api/deployment') return route.fulfill({ json: { label: 'beta' } });
    if (path === '/api/presets') return route.fulfill({ json: { presets: [] } });
    if (path === "/api/events") { events.push(request.postDataJSON().kind); return route.fulfill({ status: 204 }); }
    if (path === "/api/my/yamls" && request.method() === "GET") return route.fulfill({ json: { yamls: [saved] } });
    if (path === "/api/my/submissions") return route.fulfill({ json: { submissions: [] } });
    if (path === "/api/my/rooms") return route.fulfill({ json: { rooms: [{ id: "journey-room", name: "Journey room", status: "open", joined: true, is_host: false, submit_deadline: null }] } });
    if (path === '/api/public/rooms/journey-room') return route.fulfill({ json: { id: 'journey-room', name: 'Journey room', status: 'open', submit_deadline: '2027-01-01T12:00:00Z', yamls: [] } });
    if (!['GET', 'HEAD'].includes(request.method())) {
      writes.push({ method: request.method(), path, body: request.postDataJSON() });
      if (path.startsWith('/api/my/yamls')) return route.fulfill({ json: { ...saved, ...request.postDataJSON(), id: path.endsWith('/71') ? 71 : 72 } });
      if (path === '/api/submit/journey-room' || path === '/api/rooms/journey-room/yamls/create') return route.fulfill({ json: { player_name: 'ExistingSetup', game: 'Crash Team Racing', validation_status: 'valid' } });
      return route.fulfill({ status: 403, json: { error: 'Unexpected mutation blocked by test' } });
    }
    // Use a small representative schema, with Alpha7's archive-derived racer
    // range. The exact archive parser is independently verified by Python.
    if (path.includes('/builder-schema')) {
      const schema = process.env.CTR_REVIEW_SCHEMA ? JSON.parse(readFileSync(process.env.CTR_REVIEW_SCHEMA, 'utf8')) : {
      apworld_name: 'ctr', version: '0.2.0-alpha7', game: 'Crash Team Racing', display_name: 'Crash Team Racing',
      schema: { game: 'Crash Team Racing', ap_version: '', world_version: '', categories: ['Characters'], options: [
        { name: 'racer_locked_pads', display_name: 'Racer-Locked Warp Pads', category: 'Characters', description: 'Maximum locked pads.', type: 'range', min: 0, max: 27, default: 0 },
      ] },
      };
      return route.fulfill({ json: path.endsWith('/builder-schemas') ? [schema] : schema });
    }
    return route.fulfill({ status: 404, json: { error: 'No test fixture for this read' } });
  });
  page.on('dialog', dialog => dialog.accept());
  return { writes, events };
}

for (const context of ['public-room', 'host-room']) test(`${context} keeps destination visible and reports completion`, async ({ page }) => {
  const { writes, events } = await fixtures(page);
  await page.goto(`/yaml-builder/ctr?context=${context}&room=journey-room`);
  await expect(page.getByRole('complementary', { name: 'Submission destination' })).toContainText('Journey room');
  await expect(page.getByRole('complementary', { name: 'Submission destination' })).toContainText('Deadline');
  await page.getByRole('button', { name: 'Start with the game defaults' }).click();
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: context === 'public-room' ? 'Submit to this room' : 'Add to this room', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'ExistingSetup' })).toBeVisible();
  expect(writes[0].path).toBe(context === 'public-room' ? '/api/submit/journey-room' : '/api/rooms/journey-room/yamls/create');
  expect(events).toContain('builder_yaml_emitted');
});

test('library can send to a room and deletion has a keep option', async ({ page }) => {
  const { writes } = await fixtures(page);
  await page.goto('/my/yamls');
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Delete permanently' })).toBeVisible();
  await page.getByRole('button', { name: 'Keep this YAML' }).click();
  expect(writes).toHaveLength(0);
  await page.getByRole('button', { name: 'Send to room', exact: true }).click();
  await page.getByRole('combobox', { name: 'Destination room' }).selectOption('journey-room');
  await page.getByRole('button', { name: 'Review and submit', exact: true }).click();
  await expect(page).toHaveURL(/context=public-room&room=journey-room&from=71/);
  await expect(page.getByRole('complementary', { name: 'Submission destination' })).toContainText('Journey room');
});

test('saved raw YAML downloads without a working APWorld schema', async ({ page }) => {
  await fixtures(page);
  let schemas = 0;
  await page.route('**/api/my/yamls', route => route.fulfill({ json: { yamls: [{ id: 72, apworld_name: 'retired', version: '1', player_name: 'Retained', label: 'Original file', kind: 'advanced', yaml_content: 'name: Retained\ngame: Retired\nRetired:\n  house_rule: keep\n', outdated: false, warnings: [] }] } }));
  await page.route('**/api/apworlds/**/builder-schema*', route => { schemas++; return route.fulfill({ status: 404 }); });
  await page.goto('/my/yamls');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download saved file' }).click();
  expect((await download).suggestedFilename()).toContain('Retained');
  expect(schemas).toBe(0);
});

test('failed attachment after room creation keeps the YAML and can be retried', async ({ page }) => {
  const { events } = await fixtures(page);
  let attachmentAttempts = 0;
  await page.route('**/api/rooms', route => route.request().method() === 'POST'
    ? route.fulfill({ json: { id: 'new-journey-room', name: 'Created fixture', status: 'open' } })
    : route.fulfill({ json: [] }));
  await page.route('**/api/submit/new-journey-room', route => {
    attachmentAttempts++;
    return attachmentAttempts === 1 ? route.fulfill({ status: 503, json: { error: 'Temporary submission failure' } }) : route.fulfill({ json: { player_name: 'JourneyTest', game: 'Crash Team Racing', validation_status: 'valid' } });
  });
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7');
  await page.getByRole('button', { name: 'Start with the game defaults' }).click();
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: 'Create room with this YAML', exact: true }).click();
  await page.getByPlaceholder('Room name', { exact: true }).fill('Created fixture');
  await page.getByRole('button', { name: 'Create', exact: true }).click();
  await expect(page.getByText('Your YAML is still here.', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download .yaml', exact: true })).toBeVisible();
  expect(events).not.toContain('builder_yaml_emitted');
  await page.getByRole('button', { name: 'Retry adding YAML' }).click();
  await expect.poll(() => attachmentAttempts).toBe(2);
  await expect.poll(() => events.includes('builder_yaml_emitted')).toBe(true);
  expect(events).not.toContain('builder_abandoned');
});

test('intent entry validates invitations and preserves organizer sign-in destination', async ({ page }) => {
  await fixtures(page, false);
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Prepare a YAML', exact: true })).toHaveAttribute('href', '/yaml-builder');
  await page.getByLabel('Collection-room link').fill('https://example.org/r/unsafe');
  await page.getByRole('button', { name: 'Open invitation' }).click();
  await expect(page.getByRole('alert')).toContainText('Paste the collection-room link');
  await page.getByRole('button', { name: 'Sign in to organize a room' }).click();
  await expect(page).toHaveURL(/\/rooms$/);
});

test('sign-in draft conflicts preserve the existing account draft until chosen', async ({ page }) => {
  await fixtures(page, false);
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7');
  await page.evaluate(() => sessionStorage.setItem('ap-pie:yaml-builder:424242:standalone:standalone:ctr:0.2.0-alpha7', JSON.stringify({ playerName: 'AccountDraft', values: {}, step: 'options' })));
  await page.getByRole('button', { name: 'Start with the game defaults' }).click();
  await page.locator('input[placeholder^="Your slot name"]').fill('AnonymousDraft');
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: 'Sign in and save', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Choose which draft to continue' })).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('ap-pie:yaml-builder:424242:standalone:standalone:ctr:0.2.0-alpha7')!).playerName)).toBe('AccountDraft');
  await page.getByRole('button', { name: 'Keep my signed-in draft' }).click();
  await expect(page.locator('input[placeholder^="Your slot name"]')).toHaveValue('AccountDraft');
});

test('new edits after saving become recoverable drafts again', async ({ page }) => {
  await fixtures(page);
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7&from=71');
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.getByText('Saved to My YAMLs.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Back to options' }).click();
  await page.locator('input[placeholder^="Your slot name"]').fill('UnsavedChange');
  await page.reload();
  await expect(page.locator('input[placeholder^="Your slot name"]')).toHaveValue('UnsavedChange');
});

test('version changes require review and preserve the original entry', async ({ page }) => {
  const { writes } = await fixtures(page);
  await page.route('**/api/my/yamls', route => route.fulfill({ json: { yamls: [{ id: 71, apworld_name: 'ctr', version: '0.2.0-alpha6', player_name: 'OlderSetup', label: 'Original', kind: 'simple', values: { racer_locked_pads: true }, latest_version: '0.2.0-alpha7', outdated: true, warnings: [] }] } }));
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7&from=71');
  await expect(page.getByRole('heading', { name: 'Review the version change' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Keep v0.2.0-alpha6' })).toHaveAttribute('href', /version=0.2.0-alpha6/);
  expect(writes).toHaveLength(0);
  await page.getByRole('button', { name: 'Review a copy with v0.2.0-alpha7' }).click();
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Save to my YAMLs', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save changes', exact: true })).toHaveCount(0);
});

test('anonymous sign-in preserves edited draft and enables account save', async ({ page }) => {
  const { writes, events } = await fixtures(page, false);
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7');
  await page.getByRole('button', { name: 'Start with the game defaults' }).click();
  await page.locator('input[placeholder^="Your slot name"]').fill('BeforeLogin');
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: 'Sign in and save', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Save to my YAMLs', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Save to my YAMLs', exact: true }).click();
  await expect(page.getByText('Saved to My YAMLs.', { exact: false })).toBeVisible();
  expect(writes[0].body.player_name).toBe('BeforeLogin');
  expect(events).toContain('builder_saved');
});

test('saved setup updates the original; copy is explicit; room success is not abandonment', async ({ page }) => {
  const { writes, events } = await fixtures(page);
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7&from=71');
  await expect(page.locator('input[placeholder^="Your slot name"]')).toHaveValue('ExistingSetup');
  await page.getByRole('button', { name: 'Review YAML', exact: false }).click();
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  await expect(page.getByText('Saved to My YAMLs.', { exact: false })).toBeVisible();
  expect(writes[0].method).toBe('PATCH'); expect(writes[0].path).toBe('/api/my/yamls/71'); expect(writes[0].body.label).toBe('Weekend setup');
  await page.getByRole('button', { name: 'Save a copy', exact: true }).click();
  await expect.poll(() => writes.length).toBe(2); expect(writes[1].method).toBe('POST');
  await page.getByRole('combobox', { name: 'Room to send YAML to' }).selectOption('journey-room');
  await page.getByRole('button', { name: 'Add to room', exact: true }).click();
  await expect(page.getByText('Added ExistingSetup', { exact: false })).toBeVisible();
  await expect.poll(() => events.includes('builder_yaml_emitted')).toBe(true);
  await page.getByRole('button', { name: 'Back', exact: true }).click();
  await page.waitForTimeout(150);
  expect(events).not.toContain('builder_abandoned');
});

test('phone has reachable progression and can export a racer lock count', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fixtures(page, false);
  await page.goto('/yaml-builder/ctr?version=0.2.0-alpha7');
  await page.getByRole('button', { name: 'Start with the game defaults' }).click();
  const next = page.getByRole('button', { name: 'Review YAML', exact: false });
  const box = await next.boundingBox(); expect(box!.y + box!.height).toBeLessThanOrEqual(844);
  await page.screenshot({ path: testInfo.outputPath('mobile-options.png') });
  const search = page.locator('input[placeholder^="Filter "]');
  if (await search.count()) await search.fill('racer_locked_pads');
  else await page.locator('summary').filter({ hasText: 'Characters' }).click();
  await page.locator('.yaml-builder-option').filter({ hasText: 'racer_locked_pads' }).locator('.range-input input[type="number"]').fill('7');
  await next.click();
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: 'Download .yaml', exact: true }).click();
  const file = await download; const stream = await file.createReadStream(); let text = ''; for await (const chunk of stream!) text += chunk.toString();
  await file.saveAs(testInfo.outputPath('ctr-racer-locks.yaml'));
  expect(text).toContain('racer_locked_pads: 7');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
