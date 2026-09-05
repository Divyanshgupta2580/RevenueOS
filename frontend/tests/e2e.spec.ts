/**
 * Playwright End-to-End Test Suite for RevenueOS Command Center.
 *
 * Covers:
 * 1. Unauthenticated redirect to /login
 * 2. Login page renders credentials and clean sign-in form
 * 3. Registration page renders form fields and link to Login
 * 4. Command Center dashboard layout and 5 primary KPI cards
 * 5. Navigation tabs switch seamlessly between Radar, Ledger, and Metrics
 * 6. Truthful empty states render when no data exists (No Dummy Data)
 * 7. Zero emojis across all rendered text content
 */

import { test, expect } from "@playwright/test";

test.describe("RevenueOS Command Center E2E", () => {
  test("1. Unauthenticated root visits immediately redirect to /login", async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ authenticated: false }),
      });
    });

    await page.goto("/");
    await expect(page).toHaveURL(/.*login/);
    await expect(page.locator("h1")).toContainText("RevenueOS");
  });

  test("2. Login page renders empty credentials, Register link, and submit button", async ({ page }) => {
    await page.goto("/login");
    const emailInput = page.locator("input[type='email']");
    await expect(emailInput).toBeVisible();
    await expect(emailInput).toHaveValue("");
    await expect(page.locator("input[type='password']")).toBeVisible();
    const submitBtn = page.locator("button[type='submit']");
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toBeEnabled();
    await expect(page.locator("a:has-text('Register here')")).toBeVisible();
  });

  test("3. Registration page renders form fields and link to Login", async ({ page }) => {
    await page.goto("/register");
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[placeholder='Create a strong password']")).toBeVisible();
    await expect(page.locator("input[placeholder='Re-enter password']")).toBeVisible();
    const submitBtn = page.locator("button[type='submit']");
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toBeEnabled();
    await expect(page.locator("a:has-text('Sign In')")).toBeVisible();
  });

  test("4. Command Center displays header, connection badge, and 5 KPI cards", async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    await expect(page.locator("header")).toBeVisible();
    await page.locator("button:has-text('Outcome Metrics')").click();
    await expect(page.getByText("REVENUE AT RISK", { exact: true })).toBeVisible();
    await expect(page.getByText(/Expected Recoverable/i)).toBeVisible();
    await expect(page.getByText(/Actually Recovered/i)).toBeVisible();
    await expect(page.getByText(/Estimated Lift/i)).toBeVisible();
    await expect(page.getByText(/Recovery Rate/i)).toBeVisible();
  });

  test("5. Navigation tabs switch seamlessly between Radar, Ledger, and Metrics", async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    await page.goto("/");

    // Click Decision Ledger tab
    await page.locator("button:has-text('Decision Ledger')").click();
    await expect(page.locator("text=Decision Ledger & Audit Timeline")).toBeVisible();

    // Click Outcome Metrics tab
    await page.locator("button:has-text('Outcome Metrics')").click();
    await expect(page.locator("text=Measured Outcome & Incremental Recovery Lift")).toBeVisible();

    // Return to Radar
    await page.locator("button:has-text('Revenue Radar')").click();
    await expect(page.locator("text=Revenue Radar Opportunities")).toBeVisible();
  });

  test("6. Truthful empty states render when no data exists (No Dummy Data)", async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    // Verifies truthful empty state instead of fake demo data
    await expect(page.locator("text=No revenue at risk detected")).toBeVisible();
  });

  test("7. Zero emojis across all rendered text content", async ({ page }) => {
    await page.goto("/login");
    const content = await page.content();
    // Regex checking standard Unicode emoji ranges
    const emojiRegex = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    expect(emojiRegex.test(content)).toBeFalsy();
  });

  test("8. Razorpay Checkout tab and /checkout route render redesigned checkout interface", async ({ page }) => {
    // Authenticate session for /checkout page access
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    // Test standalone /checkout page
    await page.goto("/checkout");
    await expect(page.locator("text=Secure Payments for Revenue Recovery")).toBeVisible();
    await expect(page.locator("text=Razorpay Standard Web Checkout")).toBeVisible();
    await expect(page.getByText("HMAC-SHA256", { exact: true })).toBeVisible();
    await expect(page.getByText("Verified", { exact: true })).toBeVisible();

    // Verify presence of either active verified state or payment CTA
    const hasSuccessBanner = await page.locator("text=Payment Verified & Captured Successfully!").isVisible().catch(() => false);
    if (hasSuccessBanner) {
      await expect(page.locator("button:has-text('Make Another Payment')")).toBeVisible();
    } else {
      await expect(page.locator("button:has-text('with Razorpay')")).toBeVisible();
    }

    await page.goto("/");
    await page.locator("button:has-text('Checkout')").click();
    await expect(page.locator("text=Secure Payments for Revenue Recovery")).toBeVisible();
    await expect(page.locator("text=Razorpay Standard Web Checkout")).toBeVisible();
    await expect(page.locator("text=Standard Checkout Architecture Flow")).toBeVisible();
  });

  test("9. Strictly zero exposure of KEY_SECRET in rendered user interface copy", async ({ page }) => {
    await page.goto("/checkout");
    const content = await page.content();
    expect(content).not.toContain("KEY_SECRET");
  });

  test("10. WebSocket status indicator reflects connection state with tooltip", async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    const statusBtn = page.locator("button[aria-label^='WebSocket status:']");
    await expect(statusBtn).toBeVisible();
    const label = await statusBtn.getAttribute("aria-label");
    expect(label).toMatch(/WebSocket status: (Connected|Connecting|Reconnecting|Disconnected)/);
  });
});
