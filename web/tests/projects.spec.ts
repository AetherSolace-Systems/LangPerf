import { test, expect } from "@playwright/test";

test("agents page shows project filter chips including default", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByRole("button", { name: /all projects/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /default/i }).first()).toBeVisible();
});

test("add-agent modal has a project select that defaults to default", async ({ page }) => {
  await page.goto("/agents");
  await page.getByRole("button", { name: /add agent/i }).click();
  const sel = page.locator("select").first();
  await expect(sel).toBeVisible();
  const val = await sel.inputValue();
  expect(val).toBe("default");
});

test("settings/projects lists the default project", async ({ page }) => {
  await page.goto("/settings/projects");
  await expect(page.getByRole("button", { name: /new project/i })).toBeVisible();
  await expect(page.getByText(/^default$/i).first()).toBeVisible();
});

test("settings/projects can create a new project", async ({ page }) => {
  await page.goto("/settings/projects");
  const uniq = `e2e-${Date.now()}`;
  await page.getByRole("button", { name: /new project/i }).click();
  await page.getByLabel(/^Name$/).fill(uniq);
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByText(uniq).first()).toBeVisible();
});
