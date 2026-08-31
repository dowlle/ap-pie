import { expect, test, type Page, type Route } from "@playwright/test";

const user = {
  id: 42,
  discord_id: "discord-42",
  discord_username: "Berry",
  is_admin: false,
  is_approved: false,
  is_owner: false,
  room_creation_blocked: false,
  created_at: "2026-08-01T12:00:00+00:00",
  deletion_requested_at: null,
  deletion_due_at: null,
};

const summary = {
  account: user,
  counts: {
    rooms: 2,
    hosted_submissions: 5,
    saved_yamls: 3,
    submissions: 4,
    presets: 1,
    room_templates: 2,
    apworld_requests: 0,
  },
  is_owner: false,
  deletion_grace_days: 7,
};

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockSignedInAccount(page: Page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") return json(route, user);
    if (url.pathname === "/api/features") {
      return json(route, { generation: false, open_room_creation: true });
    }
    if (url.pathname === "/api/deployment") return json(route, { label: "beta" });
    if (url.pathname === "/api/my/account") return json(route, summary);
    if (url.pathname === "/api/my/yamls") return json(route, { yamls: [] });
    if (url.pathname === "/api/my/submissions") return json(route, { submissions: [] });
    return json(route, { error: "not mocked" }, 404);
  });
}

test("open-access users get the complete personal account surface", async ({ page }) => {
  await mockSignedInAccount(page);
  await page.goto("/my/account");

  await expect(page.getByRole("heading", { level: 1, name: "My stuff" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Room templates" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Account" })).toHaveClass(/is-active/);
  await expect(page.getByText("Berry", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("7-day recovery period", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download my data" })).toHaveAttribute(
    "href",
    "/api/my/account/export",
  );
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("invalid personal tabs canonicalize instead of silently showing YAMLs", async ({ page }) => {
  await mockSignedInAccount(page);
  await page.goto("/my/not-a-tab");
  await expect(page).toHaveURL(/\/my\/yamls$/);
  await expect(page.getByRole("button", { name: "YAMLs" })).toHaveClass(/is-active/);
});

test("same-identity recovery is explicit and returns to the account", async ({ page }) => {
  let restored = false;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/auth/me") {
      return restored ? json(route, user) : json(route, { error: "Not authenticated" }, 401);
    }
    if (url.pathname === "/api/auth/account-recovery" && route.request().method() === "GET") {
      return json(route, {
        discord_username: "Berry",
        deletion_requested_at: "2026-08-31T12:00:00+00:00",
        deletion_due_at: "2026-09-07T12:00:00+00:00",
      });
    }
    if (url.pathname === "/api/auth/account-recovery" && route.request().method() === "POST") {
      restored = true;
      return json(route, { status: "recovered" });
    }
    if (url.pathname === "/api/features") {
      return json(route, { generation: false, open_room_creation: true });
    }
    if (url.pathname === "/api/deployment") return json(route, { label: "beta" });
    if (url.pathname === "/api/my/account") return json(route, summary);
    if (url.pathname === "/api/games") return json(route, { error: "Authentication required" }, 401);
    return json(route, { error: "not mocked" }, 404);
  });

  await page.goto("/account-recovery");
  await expect(page.getByRole("heading", { name: "Restore Berry" })).toBeVisible();
  await page.getByRole("button", { name: "Restore my account" }).click();
  await expect(page).toHaveURL(/\/my\/account\?recovered=1$/);
  await expect(page.getByText("Account restored", { exact: false })).toBeVisible();
});
