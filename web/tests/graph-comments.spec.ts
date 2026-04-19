import { test, expect } from "@playwright/test";
import { firstRunId } from "./_helpers";

test("sidebar Thread tab renders CommentThread for a selected span", async ({ page }) => {
  const tid = await firstRunId(page);
  await page.goto(`/t/${tid}`);

  // First click the graph view so a span is selected (initialId on SelectionProvider already picks the first span)
  await page.getByRole("button", { name: /^graph$/i }).click();
  await page.getByRole("tab", { name: /thread/i }).click();

  // CommentThread renders "Comments" heading (see web/components/collab/comment-thread.tsx)
  await expect(page.getByText(/^Comments$/i)).toBeVisible();
});
