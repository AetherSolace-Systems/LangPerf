import { test, expect } from "@playwright/test";

test.describe("App shell", () => {
  test("top bar renders logo with teal `lang` + peach `perf`", async ({ page }) => {
    await page.goto("/");
    const logo = page.locator("header a[href='/']").first();
    await expect(logo).toBeVisible();
    await expect(logo.locator("span.text-aether-teal")).toHaveText("lang");
    await expect(logo.locator("span.text-peach-neon")).toHaveText("perf");
  });

  test("rail shows primary nav items, with v2 items disabled", async ({ page }) => {
    await page.goto("/");
    const nav = page.getByTestId("rail-nav");

    // Primary items (all clickable). Each link text is glyph+label (e.g. "□dash"),
    // so match the label substring rather than anchoring with ^…$.
    for (const label of ["dash", "agents", "history", "logs", "config"]) {
      const item = nav.locator("a").filter({ hasText: new RegExp(label, "i") });
      await expect(item).toBeVisible();
    }

    // v2 items render as <div> not <a>, with aria-disabled + title.
    for (const label of ["evals", "data"]) {
      const item = nav.locator("div[aria-disabled='true']").filter({
        hasText: new RegExp(label, "i"),
      });
      await expect(item).toBeVisible();
      await expect(item).toHaveAttribute("title", /v2/);
    }
  });

  test("home rail item is active on `/`", async ({ page }) => {
    await page.goto("/");
    // Link text is glyph+label ("□dash"), match label substring.
    const home = page.getByTestId("rail-nav").locator("a").filter({ hasText: /dash/i });
    await expect(home).toHaveClass(/text-aether-teal/);
  });
});

test.describe("Redirects", () => {
  test("/settings redirects to /settings/log-forwarding", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings\/log-forwarding$/);
  });

  test("/r/:id redirects to /t/:id", async ({ page }) => {
    // Fake id — redirect happens server-side regardless of existence
    await page.goto("/r/00000000-0000-0000-0000-000000000000");
    await expect(page).toHaveURL(/\/t\/00000000-0000-0000-0000-000000000000$/);
  });

  test("/agents/[name] redirects to /overview", async ({ page }, testInfo) => {
    // Use a real agent since /agents/[name] fetches getAgent which 404s on missing.
    const resp = await page.request.get("http://localhost:4318/api/agents");
    const agents = (await resp.json()) as { name: string }[];
    test.skip(agents.length === 0, "no agents seeded");
    const name = agents[0].name;
    await page.goto(`/agents/${encodeURIComponent(name)}`);
    await expect(page).toHaveURL(new RegExp(`/agents/${encodeURIComponent(name)}/overview$`));
  });
});

test.describe("404s", () => {
  test("/agents/<real>/bogus returns 404", async ({ page }) => {
    const resp = await page.request.get("http://localhost:4318/api/agents");
    const agents = (await resp.json()) as { name: string }[];
    test.skip(agents.length === 0, "no agents seeded");
    const response = await page.goto(`/agents/${agents[0].name}/bogus-tab`);
    expect(response?.status()).toBe(404);
  });

  test("/settings/billing is 404 (v2)", async ({ page }) => {
    const response = await page.goto("/settings/billing");
    expect(response?.status()).toBe(404);
  });
});
