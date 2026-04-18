import { expect, test } from "@playwright/test";

test("trajectory detail page renders a rewrites section", async ({ page }) => {
  // Assumes bootstrap signup + seeded trajectory data
  await page.goto("/");
  // Navigate to any trajectory
  await page.locator("a[href^='/t/']").first().click();
  await expect(page.getByText(/rewrites/i).first()).toBeVisible();
});
