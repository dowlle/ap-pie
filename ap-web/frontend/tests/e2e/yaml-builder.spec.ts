import { expect, test, type Page } from "@playwright/test";
import { load } from "js-yaml";

const CUSTOM_TRACK = {
  lev_sha256: "96ad9f74f51a02eafcc207cd02c97052d674c950e0f24b6440a227494a705fe8",
  vrm_sha256: "2dcaa0fe93359c7ae00fb93842a581210e0dcc2db73f4de43508375834092e83",
  laps: 7,
  replaces: "purple_gem_cup",
  flags: {
    crates: true,
    ctr_letters: true,
    relic_crates: true,
    ai_nav: true,
    minimap: false,
    ghosts: false,
    spawns: 8,
    checkpoints: 35,
  },
};

async function mockDictKindsSchema(page: Page) {
  await page.route("**/api/apworlds/dict-kinds-fixture/builder-schema?*", (route) => route.fulfill({
    json: {
      game: "Dict Kinds Fixture",
      apworld_name: "dict-kinds-fixture",
      display_name: "Dict Kinds Fixture",
      version: "0.2.0-alpha6",
      schema: {
        _format_version: 3,
        game: "Dict Kinds Fixture",
        ap_version: "0.6.7",
        world_version: "0.2.0-alpha6",
        categories: ["Composite"],
        options: [
          {
            name: "custom_tracks",
            display_name: "Custom Tracks",
            type: "dict",
            dict_kind: "mapping",
            valid_keys: ["baby-t-park"],
            category: "Composite",
            description: "Nested custom track metadata.",
            default: {},
          },
          {
            name: "trap_weights",
            display_name: "Trap Weights",
            type: "dict",
            dict_kind: "counter",
            valid_keys: ["slow", "spin"],
            category: "Composite",
            description: "Numeric trap weights.",
            default: { slow: 2, spin: 1 },
          },
          {
            name: "requirement_weights",
            display_name: "Requirement Weights",
            type: "dict",
            dict_kind: "mapping",
            mapping_value_kind: "number",
            valid_keys: ["easy_requirement", "hard_requirement"],
            category: "Composite",
            description: "Flat numeric requirement weights.",
            default: {},
          },
          {
            name: "legacy_mapping",
            display_name: "Legacy Mapping",
            type: "dict",
            valid_keys: ["known-key"],
            category: "Composite",
            description: "Cached schema without dict_kind.",
            default: {},
          },
        ],
      },
    },
  }));
}

async function openCtrBuilder(page: Page, expectDesktopLiveEditor = true) {
  await page.goto("/yaml-builder/ctr?version=0.1.5");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  if (expectDesktopLiveEditor) {
    await expect(page.locator(".yaml-builder-live-editor")).toBeVisible();
  }
}

test("YAML edits lock the form until they sync", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  const player = page.locator('input[placeholder^="Your slot name"]');
  await editor.fill((await editor.inputValue()).replace("name: Player1", "name: RaceSafe"));

  await expect(player).toBeDisabled();
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Synced");
  await expect(player).toBeEnabled();
  await expect(player).toHaveValue("RaceSafe");
});

test("syntax errors block every final action", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(`${await editor.inputValue()}\nbroken: [`);
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Needs attention");
  await page.getByRole("button", { name: "Review YAML" }).click();

  await expect(page.getByRole("button", { name: "Download .yaml" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save to my YAMLs" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save as preset" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Back to options" })).toBeEnabled();
});

test("schema warnings require acknowledgement and rebuild normalizes", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(
    (await editor.inputValue()).replace(
      "oxide_final_challenge_relic_count: 18",
      "oxide_final_challenge_relic_count: 99",
    ),
  );
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Needs attention");
  await page.getByRole("button", { name: "Review YAML" }).click();
  const download = page.getByRole("button", { name: "Download .yaml" });
  await expect(download).toBeDisabled();
  await page.getByRole("button", { name: "Continue with this warning" }).click();
  await expect(download).toBeEnabled();

  await page.getByRole("button", { name: "Discard edits and rebuild from the form" }).click();
  await expect(editor).toHaveValue(/oxide_final_challenge_relic_count: 18/);
  await expect(editor).not.toHaveValue(/oxide_final_challenge_relic_count: 99/);
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Synced");
});

test("the editor enforces the 64 KiB output boundary", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(`${await editor.inputValue()}\n# ${"x".repeat(66_000)}`);
  await expect(page.locator(".yaml-builder-live-note")).toContainText("larger than 64 KiB");
  await page.getByRole("button", { name: "Review YAML" }).click();
  await expect(page.getByRole("button", { name: "Download .yaml" })).toBeDisabled();
});

test("highlighting and viewport sizing remain aligned with the editor", async ({ page }) => {
  await openCtrBuilder(page);
  const shell = page.locator(".yaml-builder-live-editor-shell");
  await expect(shell.locator(".yaml-builder-live-highlight span")).not.toHaveCount(0);
  const dimensions = await shell.evaluate((element) => {
    const editor = element.querySelector("textarea");
    return editor ? { clientHeight: editor.clientHeight, scrollHeight: editor.scrollHeight } : null;
  });
  expect(dimensions).not.toBeNull();
  expect(dimensions!.clientHeight).toBe(dimensions!.scrollHeight);
});

test("form edits update YAML without removing comments or custom values", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(
    (await editor.inputValue()).replace(
      "Crash Team Racing:\n",
      "Crash Team Racing:\n  # Keep this organizer note\n  custom_house_rule: enabled\n",
    ),
  );
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Custom values");

  await page.locator('input[placeholder^="Your slot name"]').fill("PreservedPlayer");
  await expect(editor).toHaveValue(/name: PreservedPlayer/);
  await expect(editor).toHaveValue(/# Keep this organizer note/);
  await expect(editor).toHaveValue(/custom_house_rule: enabled/);
});

test("weighted YAML values remain intact when another form field changes", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(
    (await editor.inputValue()).replace(
      "oxide_final_challenge_relic_count: 18",
      "oxide_final_challenge_relic_count: {18: 50, 15: 50}",
    ),
  );
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Custom values");
  await page.locator('input[placeholder^="Your slot name"]').fill("WeightedPlayer");
  await expect(editor).toHaveValue(/name: WeightedPlayer/);
  await expect(editor).toHaveValue(/oxide_final_challenge_relic_count:\n\s+"15": 50\n\s+"18": 50/);
});

test("free-form list options preserve commas while typing", async ({ page }) => {
  await page.route("**/api/apworlds/freeform-fixture/builder-schema?*", (route) => route.fulfill({
    json: {
      game: "Freeform Fixture",
      apworld_name: "freeform-fixture",
      display_name: "Freeform Fixture",
      version: "1.0.0",
      schema: {
        game: "Freeform Fixture",
        ap_version: "0.6.7",
        world_version: "1.0.0",
        categories: ["Lists"],
        options: [{
          name: "aliases",
          display_name: "Aliases",
          type: "list",
          category: "Lists",
          description: "Ordered aliases.",
          default: ["Kanto"],
        }],
      },
    },
  }));
  await page.goto("/yaml-builder/freeform-fixture?version=1.0.0");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();

  const aliases = page.getByRole("textbox", { name: "Aliases", exact: true });
  await aliases.fill("");
  await aliases.pressSequentially("Kanto, Johto, Hoenn");

  await expect(aliases).toHaveValue("Kanto, Johto, Hoenn");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(
    /aliases:\n\s+- Kanto\n\s+- Johto\n\s+- Hoenn/,
  );
});

test("machine-readable OptionSet keys render Pokepelago Regions as choices", async ({ page }) => {
  await page.goto("/yaml-builder/pokepelago?version=0.6.3");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();

  await expect(page.getByRole("checkbox", { name: "Kanto", exact: true })).toBeChecked();
  const johto = page.getByRole("checkbox", { name: "Johto", exact: true });
  await johto.check();
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(
    /regions:\n\s+- Kanto\n\s+- Johto/,
  );
  await expect(page.getByText(/ONLY ignored if you set.*random_region_count/s)).toBeVisible();
});

test("structured composite options only commit valid YAML fragments", async ({ page }) => {
  await page.route("**/api/apworlds/composite-fixture/builder-schema?*", (route) => route.fulfill({
    json: {
      game: "Composite Fixture",
      apworld_name: "composite-fixture",
      display_name: "Composite Fixture",
      version: "1.0.0",
      schema: {
        game: "Composite Fixture",
        ap_version: "0.6.7",
        world_version: "1.0.0",
        categories: ["Composite"],
        options: [
          {
            name: "rules",
            display_name: "Rules",
            type: "dict",
            category: "Composite",
            description: "Arbitrary nested mapping.",
            default: { mode: "safe", weights: { rare: 1 } },
          },
          {
            name: "stages",
            display_name: "Stages",
            type: "list",
            category: "Composite",
            description: "Structured ordered list.",
            default: [{ name: "first", checks: 2 }],
          },
        ],
      },
    },
  }));
  await page.goto("/yaml-builder/composite-fixture?version=1.0.0");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();

  const rules = page.getByRole("textbox", { name: "Rules", exact: true });
  const editor = page.locator(".yaml-builder-live-editor");
  await rules.fill("mode: [");
  await expect(page.getByText(/Enter a valid YAML mapping/)).toBeVisible();
  await expect(editor).toHaveValue(/rules:\n\s+mode: safe/);

  await rules.fill("mode: fast\nweights:\n  rare: 3");
  await expect(page.getByText(/Enter a valid YAML mapping/)).toBeHidden();
  await expect(editor).toHaveValue(/rules:\n\s+mode: fast\n\s+weights:\n\s+rare: 3/);

  const stages = page.getByRole("textbox", { name: "Stages", exact: true });
  await stages.fill("- name: first\n  checks: 4\n- name: final\n  checks: 8");
  await expect(editor).toHaveValue(/stages:\n\s+- name: first\n\s+checks: 4\n\s+- name: final\n\s+checks: 8/);
});

test("dict controls use explicit mapping and counter semantics", async ({ page }) => {
  await mockDictKindsSchema(page);
  await page.goto("/yaml-builder/dict-kinds-fixture?version=0.2.0-alpha6");
  await page.getByRole("button", { name: "Start with the game defaults" }).click();

  const customTracks = page.locator(".yaml-builder-option").filter({ hasText: "Custom Tracks" });
  await expect(customTracks.getByRole("textbox", { name: "Custom Tracks" })).toBeVisible();
  await expect(customTracks.locator('input[type="number"]')).toHaveCount(0);

  const trapWeights = page.locator(".yaml-builder-option").filter({ hasText: "Trap Weights" });
  await expect(trapWeights.locator('input[type="number"]')).toHaveCount(2);
  await expect(trapWeights.locator('input[type="number"]').nth(0)).toHaveValue("2");
  await expect(trapWeights.locator('input[type="number"]').nth(1)).toHaveValue("1");

  const requirementWeights = page.locator(".yaml-builder-option").filter({ hasText: "Requirement Weights" });
  await expect(requirementWeights.locator('[data-editor-kind="weight-map"]')).toBeVisible();
  await expect(requirementWeights.locator('input[type="number"]')).toHaveCount(2);
  await expect(requirementWeights.locator('input[type="number"]').nth(0)).toHaveValue("0");
  await requirementWeights.locator('input[type="number"]').nth(0).fill("7");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/requirement_weights:\n\s+easy_requirement: 7/);

  const legacyMapping = page.locator(".yaml-builder-option").filter({ hasText: "Legacy Mapping" });
  await expect(legacyMapping.getByRole("textbox", { name: "Legacy Mapping" })).toBeVisible();
  await expect(legacyMapping.locator('input[type="number"]')).toHaveCount(0);
});

test("nested OptionDict YAML survives form editing, YAML loading, and rebuild", async ({ page }) => {
  await mockDictKindsSchema(page);
  const url = "/yaml-builder/dict-kinds-fixture?version=0.2.0-alpha6";
  await page.goto(url);
  await page.getByRole("button", { name: "Start with the game defaults" }).click();

  const customTracks = page.getByRole("textbox", { name: "Custom Tracks", exact: true });
  await customTracks.fill([
    "baby-t-park:",
    `  lev_sha256: ${CUSTOM_TRACK.lev_sha256}`,
    `  vrm_sha256: ${CUSTOM_TRACK.vrm_sha256}`,
    "  laps: 7",
    "  replaces: purple_gem_cup",
    "  flags:",
    "    crates: true",
    "    ctr_letters: true",
    "    relic_crates: true",
    "    ai_nav: true",
    "    minimap: false",
    "    ghosts: false",
    "    spawns: 8",
    "    checkpoints: 35",
  ].join("\n"));

  const editor = page.locator(".yaml-builder-live-editor");
  const generated = await editor.inputValue();
  expect(load(generated)).toMatchObject({
    requires: { game: { "Dict Kinds Fixture": "0.2.0" } },
    "Dict Kinds Fixture": {
      custom_tracks: { "baby-t-park": CUSTOM_TRACK },
    },
  });

  // Exercise the opposite direction from a clean form: load the complete
  // manager-shaped YAML, let it sync into form state, then rebuild it.
  await page.evaluate(() => sessionStorage.clear());
  await page.goto(url);
  await page.getByRole("button", { name: "Start with the game defaults" }).click();
  await page.locator(".yaml-builder-live-editor").fill(generated);
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Synced");
  await page.getByRole("button", { name: "Review YAML" }).click();
  await page.getByRole("button", { name: "Discard edits and rebuild from the form" }).click();

  const rebuilt = await page.locator(".yaml-builder-live-editor").inputValue();
  expect(load(rebuilt)).toMatchObject({
    "Dict Kinds Fixture": {
      custom_tracks: { "baby-t-park": CUSTOM_TRACK },
    },
  });
});

test("route drafts recover after refresh", async ({ page }) => {
  await openCtrBuilder(page);
  const player = page.locator('input[placeholder^="Your slot name"]');
  await player.fill("RecoveredDraft");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/name: RecoveredDraft/);
  page.once("dialog", (dialog) => dialog.accept());
  await page.reload();
  await expect(player).toHaveValue("RecoveredDraft");
  await expect(page.locator(".yaml-builder-live-editor")).toHaveValue(/name: RecoveredDraft/);
});

test("mobile Review exposes the editable YAML and announced status", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openCtrBuilder(page, false);
  await expect(page.locator(".yaml-builder-live")).toBeHidden();
  await page.getByRole("button", { name: "Review YAML" }).click();
  await page.getByRole("button", { name: "Edit YAML" }).click();
  const editor = page.getByRole("textbox", { name: "YAML content" });
  await expect(editor).toBeVisible();
  await editor.fill((await editor.inputValue()).replace("name: Player1", "name: MobilePlayer"));
  await expect(page.locator(".yaml-builder-manual-note")).toContainText("Form and YAML match");
});

test("editor scroll position stays synchronized with its highlight layer", async ({ page }) => {
  await openCtrBuilder(page);
  const editor = page.locator(".yaml-builder-live-editor");
  await editor.fill(`${await editor.inputValue()}\n# ${"wide-value-".repeat(80)}\n${"# filler\n".repeat(80)}`);
  await expect(page.locator(".yaml-builder-sync-status")).toHaveText("Synced");
  const positions = await page.locator(".yaml-builder-live-editor-shell").evaluate((shell) => {
    const textarea = shell.querySelector("textarea")!;
    const highlight = shell.querySelector("pre")!;
    textarea.scrollTop = 240;
    textarea.scrollLeft = 180;
    textarea.dispatchEvent(new Event("scroll", { bubbles: true }));
    return {
      textareaTop: textarea.scrollTop,
      textareaLeft: textarea.scrollLeft,
      highlightTop: highlight.scrollTop,
      highlightLeft: highlight.scrollLeft,
    };
  });
  expect(positions.highlightTop).toBe(positions.textareaTop);
  expect(positions.highlightLeft).toBe(positions.textareaLeft);
});

test("keyboard order reaches options before final actions and editor focus stays visible", async ({ page }) => {
  await openCtrBuilder(page);
  const order = await page.locator(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]',
  ).evaluateAll((elements) => elements
    .filter((element) => (element as HTMLElement).offsetParent !== null)
    .map((element) => ({
      text: (element.getAttribute("aria-label") || element.textContent || "").trim(),
      placeholder: element.getAttribute("placeholder") || "",
    })));
  const playerIndex = order.findIndex((item) => item.placeholder.startsWith("Your slot name"));
  const reviewIndex = order.findIndex((item) => item.text.includes("Review YAML"));
  expect(playerIndex).toBeGreaterThanOrEqual(0);
  expect(reviewIndex).toBeGreaterThan(playerIndex);

  const editor = page.locator(".yaml-builder-live-editor");
  await editor.focus();
  const colors = await editor.evaluate((element) => ({
    caret: getComputedStyle(element).caretColor,
    outline: getComputedStyle(element).outlineColor,
    selection: getComputedStyle(element, "::selection").backgroundColor,
  }));
  expect(colors.caret).not.toBe("rgba(0, 0, 0, 0)");
  expect(colors.outline).not.toBe("rgba(0, 0, 0, 0)");
  expect(colors.selection).not.toBe("rgba(0, 0, 0, 0)");
});
