import { expect, test } from "@playwright/test";

test("trajectory detail page renders a rewrites section", async ({ page }) => {
  // Assumes bootstrap signup + seeded trajectory data. Dashboard links to runs
  // via /r/<id> (redirects to /t/<id>); history table links via /r/<id> too.
  await page.goto("/history");
  await page.locator("a[href^='/r/']").first().click();
  await expect(page.getByText(/rewrites/i).first()).toBeVisible();
});
