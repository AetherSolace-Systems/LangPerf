import { test, expect } from "@playwright/test";

test.describe("Dashboard /", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("breadcrumb shows 'Dashboard'", async ({ page }) => {
    await expect(page.getByText("Dashboard", { exact: true }).first()).toBeVisible();
  });

  test("'ingest ok' chip is visible", async ({ page }) => {
    await expect(page.getByText("ingest ok")).toBeVisible();
  });

  test("KPI strip — 5 tiles with uppercase-mono labels and values", async ({ page }) => {
    // Each tile label is uppercase mono; values are numbers or "—"
    const kpiGrid = page.locator(".grid.grid-cols-5").first();
    await expect(kpiGrid).toBeVisible();

    // Check each expected label (case-insensitive, since they're uppercase in CSS)
    for (const label of ["agents", "error rate", "p95 latency", "flagged"]) {
      await expect(kpiGrid.getByText(new RegExp(label, "i"))).toBeVisible();
    }
    // "runs · <window>" tile — matches any window
    await expect(kpiGrid.getByText(/runs\s*·/i)).toBeVisible();
  });

  test("Run volume card — title and 24 bar columns", async ({ page }) => {
    // Card title is rendered as uppercase mono text
    await expect(
      page.getByText(/Run volume · last 24h · hourly · by env/i)
    ).toBeVisible();

    // StackedBarChart renders one flex-1 div per bar — 24 hourly buckets
    // The outer chart container has class flex items-end h-full gap-[4px]
    const barContainer = page
      .locator(".flex.items-end.h-full")
      .first();
    await expect(barContainer).toBeVisible();
    const bars = barContainer.locator(":scope > div");
    await expect(bars).toHaveCount(24);
  });

  test("Latency card — title and SVG present", async ({ page }) => {
    await expect(
      page.getByText(/Latency · p50\/p95\/p99 · (24h|7d|30d)/i)
    ).toBeVisible();

    // LineChart renders an <svg> inside the chart area
    const svg = page.locator("svg").filter({ hasNot: page.locator("polyline[points]") }).first();
    // Just assert ANY svg is present in the latency card region
    const latencyCard = page
      .locator("div")
      .filter({ hasText: /Latency · p50\/p95\/p99/i })
      .first();
    await expect(latencyCard.locator("svg").first()).toBeVisible();
  });

  test("Most ran agents card — title and at least one agent link", async ({ page }) => {
    await expect(page.getByText(/Most ran agents · /i)).toBeVisible();

    // If agents ran in-window, there should be an <a> linking to /agents/<name>
    const mostRanCard = page
      .locator("div")
      .filter({ hasText: /Most ran agents · /i })
      .first();

    const links = mostRanCard.locator("a[href^='/agents/']");
    const count = await links.count();
    // Seed data has agents — expect at least one row
    expect(count).toBeGreaterThan(0);
  });

  test("Top tools card — title and at least one tool row", async ({ page }) => {
    await expect(page.getByText(/Top tools · /i)).toBeVisible();

    const topToolsCard = page
      .locator("div")
      .filter({ hasText: /Top tools · /i })
      .first();

    // Each tool row has font-mono class and the tool name text
    const toolRows = topToolsCard.locator(".font-mono.flex-1.truncate");
    const count = await toolRows.count();
    expect(count).toBeGreaterThan(0);
  });

  test("Agent grid card — 'Your agents' title and at least 3 agent cards", async ({ page }) => {
    await expect(page.getByText("Your agents")).toBeVisible();

    // AgentGrid renders links inside a grid-cols-4 grid
    const agentGridCard = page
      .locator("div")
      .filter({ hasText: /Your agents/ })
      .first();

    const agentLinks = agentGridCard.locator("a[href^='/agents/']");
    const count = await agentLinks.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test("Recent flagged card — title is visible", async ({ page }) => {
    await expect(page.getByText("Recent flagged")).toBeVisible();
  });

  test("V2 teasers — exactly 3 cards with V2 tag and peach border", async ({ page }) => {
    // V2Card renders a div with border-l-peach-neon class directly
    const v2Cards = page.locator("div.border-l-peach-neon");
    await expect(v2Cards).toHaveCount(3);

    for (const label of ["Triage queue", "Eval regressions", "Training data export"]) {
      // Find the specific V2 card that contains the label text
      const card = v2Cards.filter({ hasText: label });
      await expect(card).toBeVisible();
      // V2 tag div inside this card (should be exactly one)
      await expect(card.locator("div.text-peach-neon").first()).toBeVisible();
    }
  });

  test("Time range picker — 3 buttons, clicking 7d updates URL", async ({ page }) => {
    for (const w of ["24h", "7d", "30d"]) {
      await expect(page.getByRole("button", { name: w })).toBeVisible();
    }

    await page.getByRole("button", { name: "7d" }).click();
    await expect(page).toHaveURL(/\?window=7d/);
  });
});
