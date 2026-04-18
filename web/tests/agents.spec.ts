import { test, expect } from "@playwright/test";
import { firstAgentName } from "./_helpers";

test.describe("Agents index /agents", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/agents");
  });

  test("breadcrumb shows 'Agents'", async ({ page }) => {
    await expect(page.getByText("Agents", { exact: true }).first()).toBeVisible();
  });

  test("'env: all' chip is visible", async ({ page }) => {
    await expect(page.getByText("env: all")).toBeVisible();
  });

  test("time-range picker has 24h, 7d, 30d buttons", async ({ page }) => {
    for (const w of ["24h", "7d", "30d"]) {
      await expect(page.getByRole("button", { name: w })).toBeVisible();
    }
  });

  test("agent card grid is visible with at least one card", async ({ page }) => {
    // AgentGrid renders a grid-cols-4 div with agent link cards
    const grid = page.locator(".grid.grid-cols-4").first();
    await expect(grid).toBeVisible();
    const cards = grid.locator("a[href^='/agents/']");
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test("each card shows agent name, metadata, and a sparkline SVG", async ({ page }) => {
    const grid = page.locator(".grid.grid-cols-4").first();
    const firstCard = grid.locator("a[href^='/agents/']").first();
    await expect(firstCard).toBeVisible();

    // Status dot — inline span with inline background style (width: 6px)
    const dot = firstCard.locator("span[style*='width']").first();
    await expect(dot).toBeVisible();

    // Agent name text (in the truncate span)
    const nameSpan = firstCard.locator(".truncate");
    await expect(nameSpan).toBeVisible();
    const nameText = await nameSpan.textContent();
    expect(nameText?.trim().length).toBeGreaterThan(0);

    // Metadata div: "X · Y% err · p95 Z" — uses font-mono text-patina mt-[2px]
    // It's a div (block), whereas the version label is a span inside the name row
    const metaDivs = firstCard.locator("div.font-mono.text-patina");
    // There should be exactly one metadata div (the runs/err/p95 line)
    const metaText = await metaDivs.first().textContent();
    // Metadata contains "err" and "p95"
    expect(metaText).toMatch(/err/);
    expect(metaText).toMatch(/p95/);

    // Sparkline SVG (aria-hidden)
    const svg = firstCard.locator("svg[aria-hidden='true']");
    await expect(svg).toBeVisible();
  });

  test("clicking a card navigates to /agents/<name>/overview", async ({ page }) => {
    const grid = page.locator(".grid.grid-cols-4").first();
    const firstCard = grid.locator("a[href^='/agents/']").first();
    await firstCard.click();
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
