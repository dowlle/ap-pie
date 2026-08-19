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
  await expect(editor).toHaveValue(/oxide_final_challenge_relic_count: \{18: 50, 15: 50\}/);
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
  await expect(page.getByRole("status")).toContainText(/Typing|Synced/);
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
