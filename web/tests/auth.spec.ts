import { expect, test } from "@playwright/test";

test.describe.serial("auth flow", () => {
  test("bootstrap signup → dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("Display name").fill("Andrew");
    await page.getByPlaceholder("Email").fill(`andrew+${Date.now()}@example.com`);
    await page.getByPlaceholder("Password").fill("correcthorsebatterystaple");
    await page.getByRole("button", { name: /create admin account/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("logout redirects to /login", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauth'd request to / redirects to /login (multi-user mode)", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});
