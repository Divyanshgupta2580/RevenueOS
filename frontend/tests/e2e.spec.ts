/**
 * Playwright End-to-End Test Suite for RevenueOS Command Center.
 *
 * Covers:
 * 1. Unauthenticated redirect to /login
 * 2. Login page renders credentials and Turnstile widget
 * 3. Missing Turnstile token blocks submission with disabled state and security error
 * 4. Command Center dashboard layout and 5 primary KPI cards
 * 5. Navigation tabs switch seamlessly between Radar, Ledger, and Metrics
 * 6. Truthful empty states render when no data exists (No Dummy Data)
 * 7. Zero emojis across all rendered text content
 */

import { test, expect } from "@playwright/test";

test.describe("RevenueOS End-to-End User Journey", () => {
  test("1. Unauthenticated access redirects to /login", async ({ page }) => {
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

  test("2. Login page renders credentials and Turnstile widget", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[type='password']")).toBeVisible();
    await expect(page.locator("button[type='submit']")).toBeVisible();
    await expect(page.locator("text=Bot Verification")).toBeVisible();
  });

  test("3. Missing Turnstile token blocks submission with disabled state and security alert", async ({ page }) => {
    await page.goto("/login");
    await page.locator("input[type='email']").fill("operator@revenueos.local");
    await page.locator("input[type='password']").fill("OperatorPass123!");

    // Button is disabled when Turnstile verification has not completed
    await expect(page.locator("button[type='submit']")).toBeDisabled();

    // Form submission without token triggers client-side validation alert
    await page.locator("form").dispatchEvent("submit");
    await expect(page.locator("text=Please complete the Cloudflare security verification.")).toBeVisible();
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
    await expect(page.getByText("Revenue at Risk", { exact: true })).toBeVisible();
    await expect(page.locator("text=Expected Recoverable")).toBeVisible();
    await expect(page.locator("text=Actually Recovered")).toBeVisible();
    await expect(page.locator("text=Estimated Lift")).toBeVisible();
    await expect(page.locator("text=Recovery Rate")).toBeVisible();
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

  test("8. Razorpay Checkout tab and /checkout route render standard checkout interface", async ({ page }) => {
    // Test standalone /checkout page
    await page.goto("/checkout");
    await expect(page.locator("text=Razorpay Standard Web Checkout")).toBeVisible();
    await expect(page.locator("button:has-text('Pay ₹500.00 with Razorpay')")).toBeVisible();
    await expect(page.locator("text=HMAC-SHA256 Verified")).toBeVisible();

    // Test dashboard Checkout tab
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
    await page.locator("button:has-text('Checkout')").click();
    await expect(page.locator("text=Razorpay Standard Web Checkout")).toBeVisible();
    await expect(page.locator("text=Standard Checkout Architecture Flow")).toBeVisible();
  });
});
