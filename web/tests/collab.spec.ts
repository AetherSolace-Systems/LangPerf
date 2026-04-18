import { expect, test } from "@playwright/test";

test("comment and resolve on a span", async ({ page }) => {
  // Assumes bootstrap signup + seeded trajectory data (dev stack running)
  await page.goto("/");
  await page.getByRole("link", { name: /history|trajectories/i }).first().click();
  await page.locator("[data-testid^='trajectory-row-']").first().click();
  await page.locator("[data-testid^='tree-node-']").first().click();

  const body = `auto-test-${Date.now()}`;
  await page.getByPlaceholder(/leave a comment/i).fill(body);
  await page.getByRole("button", { name: /^Post$/ }).click();
  await expect(page.getByText(body)).toBeVisible();
  await page.getByText("resolve").first().click();
});

test("notifications drawer opens and lists items", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /notifications/i }).click();
  await expect(page.locator("text=No notifications").or(page.locator("li").first())).toBeVisible();
});
