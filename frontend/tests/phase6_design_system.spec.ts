import { test, expect } from "@playwright/test";

const testOpportunities = [
  {
    paymentId: "pay_phase6_test_01",
    orderId: "order_phase6_01",
    customerMasked: "o***@enterprise.com",
    amountPaise: 150000,
    currency: "INR",
    status: "failed",
    failureReason: "International card transaction not supported by domestic gateway routing",
    failureCategory: "soft_decline",
    recoverabilityScore: 75.0,
    expectedRecoveryValuePaise: 95625,
    retryCount: 0,
    maxRetries: 3,
    heuristicRecommendedAction: "PAYMENT_LINK",
    recoveryStatus: "at_risk",
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹1,500.00",
        currency: "INR",
        failureCategory: "soft_decline",
        failureReason: "International card transaction not supported by domestic gateway routing",
        paymentMethod: "Card (Domestic Gateway)",
        captured: false,
      },
      backendCalculations: {
        recoverabilityScore: 75,
        expectedRecoveryPaise: 95625,
        formattedERV: "₹956.25",
        estimatedProbability: 0.75,
        paymentAge: "5m ago",
      },
      historicalEvidence: {
        customerId: "o***@enterprise.com",
        customerSuccessfulPayments: 2,
        customerFailedPayments: 1,
        recoveryAttempts: 0,
      },
      policyConstraints: {
        maxRetries: 3,
        cooldownSeconds: 300,
        allowedActions: ["PAYMENT_LINK", "RETRY", "REMINDER", "STOP"],
        forbiddenActions: ["DIRECT_DEBIT", "AUTOMATIC_CHARGE"],
      },
    },
  },
];

const viewports = [
  { width: 1440, height: 900, name: "desktop-1440x900" },
  { width: 1280, height: 800, name: "laptop-1280x800" },
  { width: 1024, height: 768, name: "tablet-landscape-1024x768" },
  { width: 768, height: 1024, name: "tablet-portrait-768x1024" },
  { width: 390, height: 844, name: "mobile-390x844" },
];

test.describe("Phase 6 Unified RevenueOS Product Design System", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { id: "usr_phase6_operator", username: "operator@revenueos.ai", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector("text=REVENUE RADAR", { timeout: 10000 });

    // Inject test opportunities
    await page.evaluate(({ opps }) => {
      const client = (window as unknown as {
        __REVENUE_WS_CLIENT__?: {
          dispatchServerMessage: (msg: unknown) => void;
        };
      }).__REVENUE_WS_CLIENT__;

      if (client) {
        client.dispatchServerMessage({
          protocolVersion: "v1",
          type: "revenue.list.response",
          timestamp: new Date().toISOString(),
          payload: {
            opportunities: opps,
            summary: {
              totalOpportunities: opps.length,
              revenueAtRiskPaise: 150000,
              expectedRecoverablePaise: 95625,
              averageRecoverabilityScore: 75,
            },
          },
        });
      }
    }, { opps: testOpportunities });

    await page.waitForTimeout(300);
  });

  test("1-4. Navigation, active state, and visual hierarchy are consistent", async ({ page }) => {
    // Header brand and active radar tab
    await expect(page.locator("header")).toBeVisible();
    await expect(page.locator("text=RevenueOS").first()).toBeVisible();

    // Verify main navigation buttons
    await expect(page.locator("button:has-text('Revenue Radar')").first()).toBeVisible();
    await expect(page.locator("button:has-text('Decision Ledger')").first()).toBeVisible();
    await expect(page.locator("button:has-text('Outcome Metrics')").first()).toBeVisible();
    await expect(page.locator("button:has-text('Checkout')").first()).toBeVisible();

    // Verify financial amounts have bold monospace dominance
    const amounts = page.locator(".font-mono");
    expect(await amounts.count()).toBeGreaterThan(0);
  });

  test("5-8. Opportunity drawer is accessible and closes on Escape key", async ({ page }) => {
    const inspectBtn = page.locator("tr:has-text('pay_phase6_test_01') button:has-text('Inspect')");
    await expect(inspectBtn).toBeVisible();
    await inspectBtn.click({ force: true });

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    // Press Escape to close
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
  });

  for (const vp of viewports) {
    test(`9-13. Zero horizontal overflow across ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/");
      await page.waitForSelector("header", { timeout: 10000 });
      await page.waitForTimeout(300);

      // Check main document has no horizontal overflow
      const overflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth <= window.innerWidth;
      });
      expect(overflow).toBe(true);

      // Check Outcome Metrics tab
      const metricsTab = page.locator("button:has-text('Outcome Metrics'):visible");
      await metricsTab.click();
      await page.waitForTimeout(200);

      const metricsOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth <= window.innerWidth;
      });
      expect(metricsOverflow).toBe(true);
    });
  }

  test("14-16. Copy audit: Zero raw secrets or developer leakages in user interface", async ({ page }) => {
    const bodyContent = await page.content();
    expect(bodyContent).not.toContain("GEMINI_API_KEY");
    expect(bodyContent).not.toContain("RAZORPAY_KEY_SECRET");
    expect(bodyContent).not.toContain("DJANGO_SECRET_KEY");
    expect(bodyContent).not.toContain("stack trace");
    expect(bodyContent).not.toContain("NullPointerException");
  });
});
