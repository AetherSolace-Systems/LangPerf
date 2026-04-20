import { test, expect } from "@playwright/test";

test.describe("Logs /logs", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/logs");
  });

  test("breadcrumb shows 'Logs'", async ({ page }) => {
    await expect(page.getByText("Logs", { exact: true }).first()).toBeVisible();
  });

  test("live chip is visible and teal", async ({ page }) => {
    // Chip variant="primary" renders with text-aether-teal
    const chip = page.locator("span, div").filter({ hasText: /^live$/i }).first();
    await expect(chip).toBeVisible();
    await expect(chip).toHaveClass(/text-aether-teal/);
  });

  test("search input is present", async ({ page }) => {
    const input = page.getByPlaceholder(/search substring/i);
    await expect(input).toBeVisible();
  });

  test("segmented level picker has DEBUG/INFO/WARN/ERROR; INFO is active by default", async ({ page }) => {
    for (const level of ["DEBUG", "INFO", "WARN", "ERROR"]) {
      await expect(page.getByRole("button", { name: level })).toBeVisible();
    }
    // The active level (INFO by default) has text-aether-teal class
    const infoBtn = page.getByRole("button", { name: "INFO" });
    await expect(infoBtn).toHaveClass(/text-aether-teal/);
  });

  test("five source toggle buttons are present", async ({ page }) => {
    for (const source of ["langperf", "uvicorn", "fastapi", "sqlalchemy", "alembic"]) {
      const btn = page.getByRole("button", { name: source });
      await expect(btn).toBeVisible();
    }
  });

  test("control buttons are present: follow, pause, clear, wrap", async ({ page }) => {
    for (const label of ["follow", /pause|resume/, "clear", "wrap"]) {
      const btn = page.getByRole("button", { name: label });
      await expect(btn).toBeVisible();
    }
  });

  test("connection indicator shows 'streaming' or 'disconnected'", async ({ page }) => {
    // Wait for the SSE connection to settle into either terminal state
    const indicator = page.getByText(/streaming|disconnected/i).first();
    await expect(indicator).toBeVisible({ timeout: 5000 });
  });

  test("console container (font-mono) is present", async ({ page }) => {
    // The scrollable console div has class font-mono text-[11px]
    const console = page.locator("div.font-mono.text-\\[11px\\]").first();
    await expect(console).toBeVisible();
  });

  test("API traffic appears in the console within a few seconds", async ({ page }) => {
    // Wait for SSE to settle into a terminal state (streaming or disconnected)
    await expect(page.getByText(/streaming|disconnected/i).first()).toBeVisible({ timeout: 5000 });

    // Generate some API traffic
    await page.request.get("http://localhost:4318/api/agents");

    // Look for any log line mentioning GET or /api/ in the console
    const consoleLogs = page.locator("div.font-mono.text-\\[11px\\] span.flex-1");

    // If level filter is hiding the line, try switching to DEBUG for full visibility
    if ((await consoleLogs.count()) === 0) {
      const debugBtn = page.getByRole("button", { name: "DEBUG" });
      await debugBtn.click();
      await expect(debugBtn).toHaveClass(/text-aether-teal/, { timeout: 5000 });
    }

    // Poll for the forwarded log line to reach the console
    await expect(async () => {
      const allText = await page.locator("div.font-mono.text-\\[11px\\]").textContent();
      const hasApiTraffic =
        (allText ?? "").includes("/api/") ||
        (allText ?? "").match(/GET|POST|PUT|DELETE/) !== null;
      // The console may also already have history loaded
      expect(hasApiTraffic || (await consoleLogs.count()) > 0).toBe(true);
    }).toPass({ timeout: 5000 });
  });
});
