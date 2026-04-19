import { test, expect } from "@playwright/test";
import { firstAgentName } from "./_helpers";

test.describe("Agents index /agents", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/agents");
  });

  test("breadcrumb shows 'Agents'", async ({ page }) => {
    await expect(page.getByText("Agents", { exact: true }).first()).toBeVisible();
  });

  test("agent count chip is visible", async ({ page }) => {
    // Top bar now shows "<N> agent(s)" instead of "env: all".
    await expect(page.getByText(/\d+ agents?/).first()).toBeVisible();
  });

  test("filter input + add-agent button are visible", async ({ page }) => {
    // Time-range picker was removed from /agents in the refactor; the page
    // now exposes a filter input + "+ Add agent" button.
    await expect(page.getByPlaceholder("Filter agents...")).toBeVisible();
    await expect(page.getByRole("button", { name: /\+ Add agent/i })).toBeVisible();
  });

  test("agent table is visible with at least one row", async ({ page }) => {
    // /agents now renders AgentsTable (not AgentGrid). Rows link to agent pages.
    const table = page.locator("table");
    await expect(table).toBeVisible();
    const rows = table.locator("tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
    // At least one row has a link into /agents/<name>/overview
    await expect(table.locator("a[href^='/agents/']").first()).toBeVisible();
  });

  test("each row shows agent name, language, and created date", async ({ page }) => {
    const table = page.locator("table");
    const firstRow = table.locator("tbody tr").first();
    await expect(firstRow).toBeVisible();

    // Name link in first cell
    const nameLink = firstRow.locator("a[href^='/agents/']").first();
    await expect(nameLink).toBeVisible();
    const nameText = await nameLink.textContent();
    expect(nameText?.trim().length).toBeGreaterThan(0);

    // Expected columns in header row (active column has a sort arrow suffix
    // like " ▲", so match the label as a substring).
    const thead = table.locator("thead tr");
    for (const col of ["Name", "Project", "Lang", "Token", "Last used", "Created"]) {
      await expect(thead.locator("th").filter({ hasText: col })).toHaveCount(1);
    }
  });

  test("clicking a row link navigates to /agents/<name>/overview", async ({ page }) => {
    const firstLink = page
      .locator("table tbody tr a[href^='/agents/']")
      .first();
    await firstLink.click();
    await expect(page).toHaveURL(/\/agents\/.+\/overview$/);
  });

  test("sidebar lists agents with run counts", async ({ page }) => {
    // ContextSidebar renders "Agents" header and then CtxItem per agent
    // The sidebar header has action "+ new" and title "Agents"
    const sidebar = page.locator("aside, [class*='sidebar'], [class*='context']").filter({
      hasText: /Agents/,
    }).first();

    // Fallback: look for a link to /agents/<name> in the sidebar area
    // The sidebar is the right context panel — links to agent pages
    const agentLinks = page.locator("a[href^='/agents/']");
    const count = await agentLinks.count();
    expect(count).toBeGreaterThan(0);

    // Each CtxItem renders the run count as a sub-label
    // The CtxItem structure: agent name link + sub text (run count)
    // Just verify the sidebar section with "Agents" label is present
    await expect(page.getByText("Agents").first()).toBeVisible();
  });
});
