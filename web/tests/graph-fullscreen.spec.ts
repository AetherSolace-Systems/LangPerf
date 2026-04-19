import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("F key toggles full-screen; Esc exits", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  await page.keyboard.press("f");
  await expect(page.locator('[data-fs="1"]')).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator('[data-fs="0"]')).toBeVisible();
});

test("floating inspector appears when a node is selected in fullscreen", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  // Enter fullscreen
  await page.keyboard.press("f");
  // Ensure we're on graph view (in fullscreen the graph should be the only thing rendered)
  // Click any node to select it
  await page.locator('[data-node-kind]').first().click();

  await expect(page.locator('[data-floating-inspector]')).toBeVisible();
});
