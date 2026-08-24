import { expect, test, type Page } from "@playwright/test";

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
