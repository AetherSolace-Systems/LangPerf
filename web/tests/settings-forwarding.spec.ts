import { test, expect } from "@playwright/test";

test.describe("Settings → Log forwarding /settings/log-forwarding", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings/log-forwarding");
  });

  test("H1 reads 'Log forwarding'", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1, name: /Log forwarding/i })).toBeVisible();
  });

  test("Local file target section is present without stub badge", async ({ page }) => {
    const localFileSection = page.locator("section").filter({ hasText: /Local file/i }).first();
    await expect(localFileSection).toBeVisible();
    // Local file does NOT have the stub badge
    await expect(
      localFileSection.locator("span").filter({ hasText: /^stub$/i })
    ).not.toBeVisible();
  });

  test("Datadog target section has stub badge", async ({ page }) => {
    const section = page.locator("section").filter({ hasText: /Datadog/i }).first();
    await expect(section).toBeVisible();
    await expect(section.locator("span").filter({ hasText: /^stub$/i })).toBeVisible();
  });

  test("Grafana Loki target section has stub badge", async ({ page }) => {
    const section = page.locator("section").filter({ hasText: /Grafana Loki/i }).first();
    await expect(section).toBeVisible();
    await expect(section.locator("span").filter({ hasText: /^stub$/i })).toBeVisible();
  });

  test("Generic OTLP target section has stub badge", async ({ page }) => {
    const section = page.locator("section").filter({ hasText: /Generic OTLP/i }).first();
    await expect(section).toBeVisible();
    await expect(section.locator("span").filter({ hasText: /^stub$/i })).toBeVisible();
  });

  test("'What gets forwarded' card has 4 toggles", async ({ page }) => {
    const whatSection = page.locator("section").filter({
      hasText: /What gets forwarded/i,
    }).first();
    await expect(whatSection).toBeVisible();
    for (const label of [
      "Server logs",
      "Trace events (new run, flagged, error)",
      "Full trajectory payloads (noisy)",
      "SDK-client diagnostic logs",
    ]) {
      await expect(whatSection.getByText(label, { exact: true })).toBeVisible();
    }
  });

  test("save button reads 'no changes' initially", async ({ page }) => {
    const btn = page.getByRole("button", { name: /no changes/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeDisabled();
  });

  test("toggling Local file enable makes form dirty and button becomes 'save'", async ({ page }) => {
    // The Local file section has the enable Toggle with label "enforcing"
    // Toggle renders as a <button> containing "enforcing" or "off" text
    const localFileSection = page.locator("section").filter({ hasText: /Local file/i }).first();
    // Find the enable/disable toggle button — it has text "enforcing" or "off" (the label)
    // and contains a rounded-full span (the pill track)
    const enableToggle = localFileSection.locator("button").filter({
      hasText: /^enforcing$|^off$/i,
    }).first();
    await enableToggle.click();

    // After toggle, form is dirty — save button becomes "save" and enabled
    const saveBtn = page.getByRole("button", { name: /^save$/i });
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toBeEnabled();
  });
});

test.describe("Settings sidebar nav", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings/log-forwarding");
  });

  test("sidebar shows 7 real settings sections under their groups", async ({ page }) => {
    const sidebar = page.locator("aside, [class*='context']").first();

    // Group labels
    for (const group of ["Workspace", "Observability", "Integrations"]) {
      await expect(page.getByText(group, { exact: true }).first()).toBeVisible();
    }

    // Real (non-v2) sections
    for (const label of [
      "Profile",
      "Environments",
      "Agents · auto-detected",
      "Log forwarding",
      "Agent trace export",
      "SDK keys",
      "Webhooks",
    ]) {
      await expect(page.getByRole("link", { name: label })).toBeVisible();
    }
  });

  test("v2 settings items are rendered with aria-disabled under 'Later' group", async ({ page }) => {
    // "Later" group label
    await expect(page.getByText("Later", { exact: true }).first()).toBeVisible();

    for (const label of ["Users & org", "Billing", "SSO / SAML"]) {
      const item = page.locator("div[aria-disabled]").filter({ hasText: label });
      await expect(item).toBeVisible();
    }
  });

  test("Log forwarding link is active (highlighted) in the sidebar", async ({ page }) => {
    // The active sidebar link has border-l-aether-teal and links to /settings/log-forwarding
    const activeLink = page.locator("a[href='/settings/log-forwarding'].border-l-aether-teal");
    await expect(activeLink).toBeVisible();
    await expect(activeLink).toHaveText(/Log forwarding/i);
  });
});
