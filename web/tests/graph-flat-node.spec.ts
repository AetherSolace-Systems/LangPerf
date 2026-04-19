import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("compact node has no gradient + shows kind stripe", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  // Match any step node kind (seed data may not have llm spans)
  const node = page.locator("[data-node-kind]").first();
  await expect(node).toBeVisible();

  const bg = await node.evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(bg).toBe("none");

  const borderLeft = await node.evaluate((el) => getComputedStyle(el).borderLeftWidth);
  expect(parseFloat(borderLeft)).toBeGreaterThanOrEqual(3);
});
