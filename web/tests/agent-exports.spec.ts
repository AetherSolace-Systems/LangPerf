import { test, expect } from "@playwright/test";

test("profile.md download button has attachment filename", async ({ page }) => {
  await page.goto("/agents/microservice-test/overview");
  const profileLink = page.getByRole("link", { name: /profile\.md/i });
  const href = await profileLink.getAttribute("href");
  expect(href).toContain("/api/agents/");
  expect(href).toContain("/profile.md");
});

test("failures.csv download button exists", async ({ page }) => {
  await page.goto("/agents/microservice-test/overview");
  const csvLink = page.getByRole("link", { name: /failures\.csv/i });
  const href = await csvLink.getAttribute("href");
  expect(href).toContain("/api/agents/");
  expect(href).toContain("/failures.csv");
});
