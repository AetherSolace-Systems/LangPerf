import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("?fs=1 opens in full-screen mode", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}?fs=1`);
  await expect(page.locator('[data-fs="1"]')).toBeVisible();
});

test("toggling full-screen updates URL", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);
  await page.keyboard.press("f");
  await expect(page).toHaveURL(/fs=1/);
  await page.keyboard.press("Escape");
  await expect(page).not.toHaveURL(/fs=1/);
});
