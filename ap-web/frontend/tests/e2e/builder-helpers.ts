import { expect, type Page } from "@playwright/test";

export async function openOptionCategory(page: Page, name: string) {
  const summary = page.locator(".yaml-builder-group > summary").filter({ hasText: name });
  const group = summary.locator("..");
  await expect(group).not.toHaveAttribute("open");
  await summary.click();
  await expect(group).toHaveAttribute("open", "");
}
