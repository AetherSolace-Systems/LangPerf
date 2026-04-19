import { test, expect } from "@playwright/test";
import { firstRunIdWithMinSteps } from "./_helpers";

test("clicking a node reveals inline body", async ({ page }) => {
  const tid = await firstRunIdWithMinSteps(page, 3);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  const node = page.locator('[data-node-kind]').first();
  await expect(node).toBeVisible();

  // Body not visible by default
  await expect(node.locator('[data-expanded-body]')).toHaveCount(0);

  await node.click();
  await expect(node.locator('[data-expanded-body]')).toBeVisible();
});

test("expand all reveals every node's body", async ({ page }) => {
  const tid = await firstRunIdWithMinSteps(page, 3);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  await page.getByRole("button", { name: /expand all/i }).click();
  const bodies = page.locator('[data-expanded-body]');
  const count = await bodies.count();
  expect(count).toBeGreaterThan(0);
});
