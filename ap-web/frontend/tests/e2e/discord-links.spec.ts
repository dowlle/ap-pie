import { expect, test } from "@playwright/test";
import siteLinks from "../../site-links.json" with { type: "json" };

const { discordInvite } = siteLinks;

for (const width of [390, 1440]) {
  for (const signedIn of [false, true]) {
    test(`home and Builder navigation fit at ${width}px when signed ${signedIn ? "in" : "out"}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.route("**/api/auth/me?**", (route) => signedIn
        ? route.fulfill({ json: { id: 42, discord_username: "Fixture Member", is_admin: false, is_approved: true } })
        : route.fulfill({ status: 401, json: { error: "Not logged in" } }));

      for (const path of ["/", "/yaml-builder"]) {
        await page.goto(path);
        if (path === "/") {
          const card = page.getByRole("region", { name: "Discord community" });
          await expect(card.getByText("Ask questions, report issues, and find people to play with.")).toBeVisible();
          const join = card.getByRole("link", { name: "Join Appie's Games Discord" });
          await expect(join).toHaveAttribute("href", discordInvite);
          await expect(join).toHaveAttribute("target", "_blank");
          await expect(join).toBeInViewport({ ratio: 1 });
        }

        const nav = page.getByRole("navigation", { name: "Main navigation" });
        const community = nav.getByRole("link", { name: "Community", exact: true });
        if (width === 390) {
          await expect(community).toBeHidden();
          await nav.getByRole("button", { name: "Open menu" }).click();
        }
        await expect(community).toBeVisible();
        await expect(community).toHaveAttribute("href", discordInvite);
        await expect(community).toHaveAttribute("target", "_blank");
        const auth = signedIn
          ? nav.getByRole("link", { name: "Fixture Member" })
          : nav.getByRole("button", { name: "Sign in with Discord" });
        await expect(auth).toBeVisible();
        expect(await nav.evaluate((element) => element.scrollWidth)).toBe(width);
        const positions = await Promise.all([
          nav.getByRole("link", { name: "YAML Builder" }).boundingBox(),
          community.boundingBox(),
          auth.boundingBox(),
        ]);
        for (const position of positions) {
          expect(position!.x).toBeGreaterThanOrEqual(0);
          expect(position!.x + position!.width).toBeLessThanOrEqual(width);
        }
        if (width === 1440) {
          const centers = positions.map((position) => position!.y + position!.height / 2);
          expect(Math.max(...centers) - Math.min(...centers)).toBeLessThan(2);
        }
      }
    });
  }

  test(`Flask header shows Community at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/guides");
    const community = page.getByRole("navigation").filter({ has: page.getByRole("link", { name: "YAML Builder" }) })
      .getByRole("link", { name: "Community", exact: true });
    if (width === 390) {
      await expect(community).toBeHidden();
      await page.getByRole("button", { name: "Open menu" }).click();
    }
    await expect(community).toHaveAttribute("href", discordInvite);
    await expect(community).toHaveAttribute("target", "_blank");
    await expect(community).toBeInViewport();
  });
}

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

test("clicks in Flask and React send the same anonymous event", async ({ page, context }) => {
  await context.route("https://discord.com/**", (route) => route.abort());
  await context.route("https://discord.gg/**", (route) => route.abort());
  for (const [path, linkName] of [
    ["/ctr/setup", "Archipelago Discord"],
    ["/guides", "Community"],
    ["/yaml-builder", "Community"],
    ["/", "Join Appie's Games Discord"],
    ["/", "Discord"],
  ]) {
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
