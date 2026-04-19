import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("sidebar has three tabs and defaults to Detail", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  const sb = page.locator('[data-sidebar-root]');
  await expect(sb).toBeVisible();
  await expect(sb.getByRole("tab", { name: /detail/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(sb.getByRole("tab", { name: /notes/i })).toBeVisible();
  await expect(sb.getByRole("tab", { name: /thread/i })).toBeVisible();
});

test("sidebar width persists across reload", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  await page.evaluate(() =>
    localStorage.setItem(
      "langperf.sidebar",
      JSON.stringify({ width: 380, open: true, tab: "detail" }),
    ),
  );
  await page.reload();
  const sb = page.locator('[data-sidebar-root]');
  const width = await sb.evaluate((el) => (el as HTMLElement).offsetWidth);
  expect(Math.round(width)).toBe(380);
});
