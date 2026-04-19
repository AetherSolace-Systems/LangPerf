import { test, expect } from "@playwright/test";
import { firstRunIdWithMinSteps } from "./_helpers";

test("clicking the expand caret reveals inline body", async ({ page }) => {
  const tid = await firstRunIdWithMinSteps(page, 3);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  const node = page.locator('[data-node-kind]').first();
  await expect(node).toBeVisible();
  await expect(node.locator('[data-expanded-body]')).toHaveCount(0);

  // Click the body → selects (no expand).
  await node.click();
  await expect(node.locator('[data-expanded-body]')).toHaveCount(0);

  // Click the caret (aria-label="Expand") → expands.
  await node.getByRole("button", { name: /expand/i }).click();
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
