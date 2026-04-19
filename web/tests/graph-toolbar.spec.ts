import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("graph toolbar shows expand/compact/fullscreen controls", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  // Switch to graph view (default is timeline)
  await page.getByRole("button", { name: /^graph$/i }).click();

  await expect(page.getByRole("button", { name: /expand all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /compact all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /full.?screen/i })).toBeVisible();
});
