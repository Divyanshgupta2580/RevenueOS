import { test, expect } from "@playwright/test";

const testOpportunities = [
  {
    paymentId: "pay_phase4_live_01",
    orderId: "order_phase4_01",
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

const fallbackOpportunity = {
  ...testOpportunities[0],
  recommendedIntervention: "PAYMENT_LINK",
  aiConfidence: 0.70,
  policyStatus: "APPROVED",
  policyReason: "Deterministic fallback rule applied during Gemini timeout.",
  isFallback: true,
  decisionGeneratedSeconds: 18.4,
  aiTelemetry: {
    context_build_ms: 1.2,
    gemini_request_ms: 18200.0,
    schema_validation_ms: 0.1,
    policy_validation_ms: 0.8,
    total_decision_ms: 18400.0,
  },
};

test.describe("Phase 4 AI Latency & Transparent Decision Processing UX", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { id: "usr_phase4_operator", username: "operator@revenueos.ai", role: "operator" },
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

    await page.waitForTimeout(400);
  });

  test("1-5. Opportunity drawer opens and displays evaluation controls and processing elements", async ({ page }) => {
    // Open Opportunity Drawer
    const inspectBtn = page.locator("tr:has-text('pay_phase4_live_01') button:has-text('Inspect')");
    await expect(inspectBtn).toBeVisible();
    await inspectBtn.click({ force: true });

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    // Verify Evaluate Button is present
    const evalBtn = dialog.locator("button:has-text('Evaluate with Gemini')");
    await expect(evalBtn).toBeVisible();
  });

  test("6-8. Fallback banner and latency display render with scientific honesty", async ({ page }) => {
    // Dispatch fallback opportunity
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
              totalOpportunities: 1,
              revenueAtRiskPaise: 150000,
              expectedRecoverablePaise: 95625,
              averageRecoverabilityScore: 75,
            },
          },
        });
      }
    }, { opps: [fallbackOpportunity] });

    await page.waitForTimeout(400);

    const inspectBtn = page.locator("tr:has-text('pay_phase4_live_01') button:has-text('Inspect')");
    await expect(inspectBtn).toBeVisible();
    await inspectBtn.click({ force: true });

    const dialog = page.locator("[role='dialog']");
    await expect(dialog).toBeVisible();

    // Check Fallback Disclaimer
    const fallbackBanner = dialog.locator("[data-testid='deterministic-fallback-banner']");
    await expect(fallbackBanner).toBeVisible();
    await expect(fallbackBanner).toContainText("DETERMINISTIC HEURISTIC FALLBACK ACTIVE");

    // Check Latency Badge
    const latencyBadge = dialog.locator("[data-testid='decision-latency-badge']");
    await expect(latencyBadge).toBeVisible();
    await expect(latencyBadge).toContainText("18.4s");

    // Check Telemetry Breakdown
    const telemetrySection = dialog.locator("[data-testid='latency-telemetry-breakdown']");
    await expect(telemetrySection).toBeVisible();
    await expect(telemetrySection).toContainText("Context Prep");
    await expect(telemetrySection).toContainText("Gemini LLM");

    // Zero secret leakage check
    const pageText = await page.content();
    expect(pageText).not.toContain("GEMINI_API_KEY");
    expect(pageText).not.toContain("RAZORPAY_KEY_SECRET");
    expect(pageText).not.toContain("DJANGO_SECRET_KEY");
  });
});
