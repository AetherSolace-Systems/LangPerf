import { test, expect } from "@playwright/test";

test.describe("History /history", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/history");
  });

  test("breadcrumb shows 'History'", async ({ page }) => {
    await expect(page.getByText("History", { exact: true }).first()).toBeVisible();
  });

  test("pattern input is visible with correct placeholder", async ({ page }) => {
    // Use the role + name selector to avoid matching the global search bar
    const input = page.getByRole("textbox", { name: /agent\.env\.version/i });
    await expect(input).toBeVisible();
    const placeholder = await input.getAttribute("placeholder");
    expect(placeholder).toMatch(/agent\.env\.version/);
  });

  test("runs table is rendered with expected columns", async ({ page }) => {
    const table = page.locator("table");
    await expect(table).toBeVisible();

    const headerRow = table.locator("thead tr");
    for (const col of ["Time", "ID", "Agent", "Input", "Steps", "Tokens", "Latency", "Ver", "Env", "Status"]) {
      await expect(headerRow.getByText(col, { exact: true })).toBeVisible();
    }
  });

  test("table has at least one row", async ({ page }) => {
    const rows = page.locator("table tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test("table row ID links to /r/<id>", async ({ page }) => {
    // ID column links to /r/<id>
    const idLink = page.locator("table tbody tr").first().locator("a[href^='/r/']");
    await expect(idLink).toBeVisible();
  });

  test("table row agent cell links to /agents/<name>", async ({ page }) => {
    // Agent column links to /agents/<name>
    // Find the first row that has an agent name (not a dash)
    const agentLink = page.locator("table tbody tr a[href^='/agents/']").first();
    await expect(agentLink).toBeVisible();
  });

  test("pattern input: type *.prod.* and press Enter → URL updates", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /agent\.env\.version/i });
    await input.fill("*.prod.*");
    await input.press("Enter");

    // URL should update with pattern=*.prod.* (URL-encoded)
    await expect(page).toHaveURL(/pattern=%2A\.prod\.%2A|pattern=\*\.prod\.\*/);
  });

  test("saved patterns sidebar has expected entries", async ({ page }) => {
    const patterns = ["*.*.*", "*.prod.*", "*.staging.*", "*.dev.*", "weather-*.*.*", "code-*.*.*"];
    for (const p of patterns) {
      await expect(page.getByText(p, { exact: true })).toBeVisible();
    }
  });

  test("clicking a saved pattern navigates to /history?pattern=...", async ({ page }) => {
    // Click the *.prod.* saved pattern link
    const patternLink = page.getByText("*.prod.*", { exact: true });
    await patternLink.click();

    await expect(page).toHaveURL(/pattern=%2A\.prod\.%2A|pattern=\*\.prod\.\*/);
  });
});
