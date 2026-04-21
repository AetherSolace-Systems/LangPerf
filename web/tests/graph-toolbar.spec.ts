import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("graph toolbar shows expand/compact/fullscreen controls", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  // Tree / Timeline / Graph are now independently-collapsible panes;
  // Graph is expanded by default, so its toolbar renders on load.

  await expect(page.getByRole("button", { name: /expand all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /compact all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /full.?screen/i })).toBeVisible();
});
