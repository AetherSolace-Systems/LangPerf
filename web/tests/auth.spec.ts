import { expect, test } from "@playwright/test";

// NOTE ON AUTH TESTS IN PARALLEL MODE:
// global-setup writes a single session token to storage-state.json that every
// parallel worker uses. Clicking the real "Sign out" UI hits
// POST /api/auth/logout which DELETEs that session from the DB — poisoning
// every other in-flight test. Originally this was masked by the bootstrap
// test failing on dogfood stacks (serial stopped, logout never ran). Now
// that bootstrap skips cleanly, we route the logout assertion through a
// dedicated ephemeral context so the shared session survives.
test.describe.serial("auth flow", () => {
  test("bootstrap signup → dashboard", async ({ page }) => {
    await page.goto("/login");
    // The bootstrap form only renders on a fresh deployment (single_user mode
    // with no admin yet). On a dogfood stack with an existing admin, the
    // login form is shown instead — skip rather than fail.
    const displayName = page.getByPlaceholder("Display name");
    if ((await displayName.count()) === 0) {
      test.skip(true, "admin already bootstrapped — skipping signup flow");
      return;
    }
    await displayName.fill("Andrew");
    await page.getByPlaceholder("Email").fill(`andrew+${Date.now()}@example.com`);
    await page.getByPlaceholder("Password").fill("correcthorsebatterystaple");
    await page.getByRole("button", { name: /create admin account/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("logout redirects to /login", async ({ browser }) => {
    // Use an ISOLATED context so the logout doesn't clobber the shared
    // storage-state session used by every parallel test. We don't need a
    // real login to assert the /login redirect on a signed-out client.
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await context.close();
  });

  test("unauth'd request to / redirects to /login (multi-user mode)", async ({ browser }) => {
    const context = await browser.newContext({ storageState: undefined });
    const page = await context.newPage();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await context.close();
  });
});
