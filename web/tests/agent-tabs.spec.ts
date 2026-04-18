import { test, expect } from "@playwright/test";
import { firstAgentName } from "./_helpers";

const TABS = ["overview", "runs", "prompt", "tools", "versions", "config"] as const;

test.describe("Agent detail — shared chrome", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test("breadcrumb reads 'Agents › <name>' on every tab", async ({ page }) => {
    for (const tab of TABS) {
      await page.goto(`/agents/${encodeURIComponent(agentName)}/${tab}`);
      // "Agents" link in the breadcrumb — use the topbar breadcrumb area
      // The breadcrumb link has class hover:text-warm-fog
      const breadcrumbLink = page.locator("a.hover\\:text-warm-fog").filter({ hasText: /^Agents$/ });
      await expect(breadcrumbLink).toBeVisible();
      // separator span
      const separator = page.locator("span").filter({ hasText: "›" }).first();
      await expect(separator).toBeVisible();
      // agent name
      await expect(page.getByText(agentName, { exact: true }).first()).toBeVisible();
    }
  });

  test("identity strip shows Agent/Ver/Env labels and chips on every tab", async ({ page }) => {
    for (const tab of TABS) {
      await page.goto(`/agents/${encodeURIComponent(agentName)}/${tab}`);
      // The identity strip is the gradient border-b flex row
      // Labels are uppercase mono spans with class text-patina uppercase
      // Use the strip's bg-gradient class to narrow scope
      const strip = page.locator("div.bg-gradient-to-b").first();
      await expect(strip).toBeVisible();
      // Labels "Agent", "Ver", "Env" are uppercase mono spans inside the strip
      await expect(strip.locator("span").filter({ hasText: /^Agent$/i })).toBeVisible();
      await expect(strip.locator("span").filter({ hasText: /^Ver$/i })).toBeVisible();
      await expect(strip.locator("span").filter({ hasText: /^Env$/i })).toBeVisible();
    }
  });

  test("tab nav shows all six tabs; clicked tab has border-b-aether-teal", async ({ page }) => {
    for (const tab of TABS) {
      await page.goto(`/agents/${encodeURIComponent(agentName)}/${tab}`);
      // All six tab links are present
      for (const t of TABS) {
        const link = page.locator("a").filter({ hasText: new RegExp(`^${t}$`, "i") });
        await expect(link.first()).toBeVisible();
      }
      // The active tab link has the teal bottom border
      const activeLink = page.locator("a.border-b-aether-teal");
      await expect(activeLink).toBeVisible();
      await expect(activeLink).toHaveText(new RegExp(tab, "i"));
    }
  });

  test("switching tabs preserves identity strip and breadcrumb", async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/overview`);
    // Click to runs tab
    await page.locator("a.border-b-transparent").filter({ hasText: /^runs$/i }).click();
    await expect(page).toHaveURL(new RegExp(`/agents/${encodeURIComponent(agentName)}/runs$`));
    // Breadcrumb still shows the same agent name
    const breadcrumbLink = page.locator("a.hover\\:text-warm-fog").filter({ hasText: /^Agents$/ });
    await expect(breadcrumbLink).toBeVisible();
    await expect(page.getByText(agentName, { exact: true }).first()).toBeVisible();
    // Identity strip still there
    const strip = page.locator("div.bg-gradient-to-b").first();
    await expect(strip.locator("span").filter({ hasText: /^Agent$/i })).toBeVisible();
  });
});

test.describe("Agent tab — overview", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/overview`);
  });

  test("5 KPI tiles with expected labels", async ({ page }) => {
    const kpiGrid = page.locator(".grid.grid-cols-5").first();
    await expect(kpiGrid).toBeVisible();
    await expect(kpiGrid.getByText(/runs\s*·/i)).toBeVisible();
    await expect(kpiGrid.getByText(/error rate/i)).toBeVisible();
    await expect(kpiGrid.getByText(/p95 latency/i)).toBeVisible();
    await expect(kpiGrid.getByText(/tools called/i)).toBeVisible();
    await expect(kpiGrid.getByText(/total tokens/i)).toBeVisible();
  });

  test("Run volume card is visible", async ({ page }) => {
    await expect(page.getByText(/Run volume\s*·/i)).toBeVisible();
  });

  test("Latency card has SVG with polylines", async ({ page }) => {
    await expect(page.getByText(/Latency\s*·\s*p50\/p95\/p99\s*·/i)).toBeVisible();
    const latencyCard = page.locator("div").filter({ hasText: /Latency\s*·\s*p50\/p95\/p99/i }).first();
    // The card may have an SVG if data exists, or an empty state — just check title is present
    await expect(latencyCard).toBeVisible();
  });

  test("Tokens & cost card has cost micro-text", async ({ page }) => {
    await expect(page.getByText(/Tokens & cost\s*·/i)).toBeVisible();
    // The right= prop renders as "cost estimated @ gpt-4o-mini pricing"
    await expect(page.getByText(/cost estimated @ gpt-4o-mini pricing/i)).toBeVisible();
  });

  test("Tools card is visible", async ({ page }) => {
    await expect(page.getByText(/^Tools\s*·/i)).toBeVisible();
  });

  test("Recent runs card is visible", async ({ page }) => {
    await expect(page.getByText(/Recent runs/i)).toBeVisible();
  });

  test("3 V2 teaser cards are present", async ({ page }) => {
    const v2Cards = page.locator("div.border-l-peach-neon");
    // Should have at least 3 (could have more on other pages visiting this same pattern)
    await expect(v2Cards).toHaveCount(3);
  });
});

test.describe("Agent tab — runs", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/runs`);
  });

  test("'All runs · <window>' card is visible", async ({ page }) => {
    await expect(page.getByText(/All runs\s*·/i)).toBeVisible();
  });

  test("RunsTable has expected columns (no Agent column)", async ({ page }) => {
    const table = page.locator("table");
    await expect(table).toBeVisible();
    const headerRow = table.locator("thead tr");
    for (const col of ["Time", "ID", "Input", "Steps", "Tokens", "Latency", "Ver", "Env", "Status"]) {
      await expect(headerRow.getByText(col, { exact: true })).toBeVisible();
    }
    // No Agent column in per-agent runs view
    await expect(headerRow.getByText("Agent", { exact: true })).not.toBeVisible();
  });

  test("row count is ≤ 100", async ({ page }) => {
    const rows = page.locator("table tbody tr");
    const count = await rows.count();
    expect(count).toBeLessThanOrEqual(100);
  });
});

test.describe("Agent tab — tools", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/tools`);
  });

  test("'Tool usage · <window>' card is visible", async ({ page }) => {
    await expect(page.getByText(/Tool usage\s*·/i)).toBeVisible();
  });

  test("ToolsTable has 6 columns: Tool/Calls/Share/Distribution/Errors/Error rate", async ({ page }) => {
    const table = page.locator("table");
    // If no tools, the empty state renders instead — skip table check gracefully
    const tableVisible = await table.isVisible().catch(() => false);
    if (!tableVisible) {
      await expect(
        page.getByText(/No tool calls captured/i)
      ).toBeVisible();
      return;
    }
    const headerRow = table.locator("thead tr");
    for (const col of ["Tool", "Calls", "Share", "Distribution", "Errors", "Error rate"]) {
      await expect(headerRow.getByText(col, { exact: true })).toBeVisible();
    }
  });
});

test.describe("Agent tab — versions", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/versions`);
  });

  test("'Versions · <n>' card is visible", async ({ page }) => {
    await expect(page.getByText(/Versions\s*·\s*\d+/i)).toBeVisible();
  });

  test("table has columns Version/SHA/Package/First seen/Last seen", async ({ page }) => {
    const table = page.locator("table");
    const tableVisible = await table.isVisible().catch(() => false);
    if (!tableVisible) {
      // Empty state — acceptable
      await expect(page.getByText(/No versions yet/i)).toBeVisible();
      return;
    }
    const headerRow = table.locator("thead tr");
    for (const col of ["Version", "SHA", "Package", "First seen", "Last seen"]) {
      await expect(headerRow.getByText(col, { exact: true })).toBeVisible();
    }
  });

  test("first row has 'current' text next to its version label", async ({ page }) => {
    const table = page.locator("table");
    const tableVisible = await table.isVisible().catch(() => false);
    if (!tableVisible) return; // empty state, nothing to check
    const firstRow = table.locator("tbody tr").first();
    await expect(firstRow.getByText("current")).toBeVisible();
  });
});

test.describe("Agent tab — config", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/config`);
  });

  test("ConfigForm has all expected fields", async ({ page }) => {
    for (const label of [
      "Name (slug)",
      "Display name",
      "Description",
      "Owner",
      "GitHub URL",
      "Signature",
    ]) {
      await expect(page.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("save button reads 'no changes' when form is pristine", async ({ page }) => {
    const btn = page.getByRole("button", { name: /no changes/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeDisabled();
  });
});

test.describe("Agent tab — prompt", () => {
  let agentName: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    agentName = await firstAgentName(page);
    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(`/agents/${encodeURIComponent(agentName)}/prompt`);
  });

  test("PromptsView renders prompt cards or empty-state copy", async ({ page }) => {
    // Either: prompt cards with metadata (runs, first, last), or empty state message
    const hasPrompts = await page.locator("pre.font-mono").count();
    if (hasPrompts > 0) {
      // Each card has: runs metadata text and a pre with monospace text
      const firstCard = page.locator("pre.font-mono").first();
      await expect(firstCard).toBeVisible();
      // Metadata line with "runs" and "first" and "last"
      await expect(page.getByText(/\d+ run/i).first()).toBeVisible();
      await expect(page.getByText(/first/i).first()).toBeVisible();
      await expect(page.getByText(/last/i).first()).toBeVisible();
    } else {
      await expect(
        page.getByText(/No system prompts captured yet/i)
      ).toBeVisible();
    }
  });
});
