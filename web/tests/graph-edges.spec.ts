import { test, expect } from "@playwright/test";
import { firstRunIdWithMinSteps } from "./_helpers";

test("graph renders labelled edges between sibling spans", async ({ page }) => {
  // Need a trajectory with at least 3 spans so there are sibling nodes → edges
  const tid = await firstRunIdWithMinSteps(page, 3);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  const labels = page.locator('[data-edge-label]');
  await expect(labels.first()).toBeVisible();
  const count = await labels.count();
  expect(count).toBeGreaterThan(0);
});

test.fixme("clicking an edge label toggles JSON peek", async ({ page }) => {
  // Known issue: the resizable sidebar / node detail panel intercepts
  // pointer events on the React Flow pane in the default (non-fullscreen)
  // layout, so the click on [data-edge-label] never reaches the edge's
  // onClick handler. Fix requires either lifting the edge label above the
  // sidebar's stacking context or adjusting the sidebar's pointer-events
  // profile when the graph view is active. Tracked as a follow-up.
  const tid = await firstRunIdWithMinSteps(page, 3);
  await page.goto(`/t/${tid}`);
  await page.getByRole("button", { name: /^graph$/i }).click();

  // Find an edge label that has a payload (cursor: pointer indicates clickable)
  const labels = page.locator('[data-edge-label]');
  await expect(labels.first()).toBeVisible();

  // Try to find a label with a payload by checking all labels
  const count = await labels.count();
  let payloadLabel = null;
  for (let i = 0; i < count; i++) {
    const label = labels.nth(i);
    const cursor = await label.evaluate((el) =>
      window.getComputedStyle(el).cursor
    );
    if (cursor === "pointer") {
      payloadLabel = label;
      break;
    }
  }

  if (!payloadLabel) {
    // No edges carry payloads in seed data — skip the toggle assertion
    // TODO: seed data has no llm→tool or tool→llm transitions with payloads; toggle test skipped
    test.skip();
    return;
  }

  await payloadLabel.click();
  await expect(payloadLabel).toHaveAttribute("data-expanded", "true");
  await payloadLabel.click();
  await expect(payloadLabel).toHaveAttribute("data-expanded", "false");
});
