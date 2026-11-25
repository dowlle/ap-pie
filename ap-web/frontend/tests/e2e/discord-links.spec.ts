import { expect, test } from "@playwright/test";
import siteLinks from "../../site-links.json" with { type: "json" };

const { discordInvite } = siteLinks;

test("public pages and both kinds of 404 show the Discord links", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("contentinfo").getByRole("link", { name: "Discord", exact: true }))
    .toHaveAttribute("href", discordInvite);

  for (const path of ["/missing-page-for-test", "/ctr/reference/missing-page-for-test", "/report-issue"]) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(path === "/report-issue" ? 200 : 404);
    await expect(page.getByRole("main").getByText("#ap-pie-website-feedback", { exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: "Appie's Games Discord" }))
      .toHaveAttribute("href", discordInvite);
  }
});

test("the YAML Builder shows CTR help only for the selected CTR world", async ({ page }) => {
  await page.goto("/yaml-builder/ctr?version=0.1.5");
  const help = page.getByText("Stuck or found a bug?", { exact: false });
  await expect(help.getByRole("link")).toHaveAttribute("href", discordInvite);
  await page.goto("/yaml-builder");
  await expect(page.getByRole("heading", { name: "Build a player YAML" })).toBeVisible();
  await expect(help).toHaveCount(0);
});

test("clicks in Flask and React send the same anonymous event", async ({ page }) => {
  await page.route("https://discord.com/**", (route) => route.abort());
  await page.route("https://discord.gg/**", (route) => route.abort());
  for (const [path, linkName] of [["/ctr/setup", "Archipelago Discord"], ["/", "Discord"]]) {
    await page.goto(path);
    const invite = page.getByRole("link", { name: linkName, exact: true });
    const outbound = page.waitForRequest((request) =>
      request.url().endsWith("/api/events") && request.postData()?.includes("discord_invite_click") === true,
    );
    await invite.click();
    const event = await outbound;
    expect(event.postDataJSON()).toEqual({ kind: "discord_invite_click" });
    expect(event.headers().referer).toBeUndefined();
  }
});
