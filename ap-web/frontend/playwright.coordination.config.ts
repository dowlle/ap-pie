import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "slot-coordination.spec.ts",
  workers: 1,
  retries: 0,
  outputDir: "/tmp/ap-pie-coordination-results",
  use: { baseURL: "http://127.0.0.1:4176", browserName: "chromium" },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4176 --strictPort",
    url: "http://127.0.0.1:4176",
    reuseExistingServer: false,
  },
});
