import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 1,
  timeout: 30_000,
  outputDir: "/tmp/ap-pie-playwright-results",
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "https://beta.ap-pie.com",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
