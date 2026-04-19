import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  // Playwright e2e specs live as *.spec.ts directly under tests/. Vitest unit
  // tests live under tests/unit/ and must NOT be picked up by Playwright.
  testMatch: "*.spec.ts",
  testIgnore: "unit/**",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  reporter: [["list"]],
  globalSetup: "./tests/global-setup.ts",
  use: {
    baseURL: "http://localhost:3030",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    storageState: "tests/.auth/storage-state.json",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
