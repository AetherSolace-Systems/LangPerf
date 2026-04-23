import { test, expect } from "@playwright/test";

test("agent overview renders 4-chart grid", async ({ page }) => {
  // Use whatever seeded agent exists; if login is required, the test may fail
  // without session setup — that's addressed by Task 14's follow-on work.
  await page.goto("/agents/microservice-test/overview");
  const charts = page.locator("[data-chart-surface]");
  await expect(charts).toHaveCount(4, { timeout: 5000 });
});

test("worklist section renders", async ({ page }) => {
  await page.goto("/agents/microservice-test/overview");
  await expect(page.locator("text=/worklist/i").first()).toBeVisible({
    timeout: 5000,
  });
});
