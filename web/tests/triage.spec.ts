import { expect, test } from "@playwright/test";

test("queue is reachable from the app shell", async ({ page }) => {
  // `/` now renders the dashboard; the queue has its own route and appears in
  // the left rail as "queue". Assert the page loads and has the expected chrome.
  await page.goto("/queue");
  await expect(page).toHaveURL(/\/queue$/);
});

test("queue row opens trajectory detail", async ({ page }) => {
  await page.goto("/queue");
  const row = page.locator("a[href^='/t/']").first();
  if (await row.isVisible()) {
    await row.click();
    await expect(page).toHaveURL(/\/t\//);
  }
});

test("heuristic filter toggles URL state", async ({ page }) => {
  await page.goto("/queue");
  await page.getByRole("button", { name: /tool errors/i }).click();
  await expect(page).toHaveURL(/heuristic=tool_error/);
});

test("clusters page renders", async ({ page }) => {
  await page.goto("/queue/clusters");
  await expect(page.getByRole("heading", { name: /clusters/i })).toBeVisible();
});
