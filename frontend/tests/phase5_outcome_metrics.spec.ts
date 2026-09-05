import { test, expect } from "@playwright/test";

const testMetricSummary = {
  revenueAtRiskPaise: 150000,
  expectedRecoverablePaise: 95625,
  actuallyRecoveredPaise: 0,
  baselineControlPaise: 12000,
  incrementalRevenuePaise: 0,
  recoveryRate: 0.0,
  activeOpportunities: 1,
  blockedActions: 1,
  observedSampleSize: 0,
  observedTransactions: 4,
  observedRecoveries: 0,
  isSampleSizeSufficient: false,
  attributionConfidence: "INSUFFICIENT SAMPLE SIZE",
  attributionStatus: "INSUFFICIENT SAMPLE SIZE",
  baselineAssumption: "Illustrative 8% heuristic control (not causal merchant history)",
  baselineComparison: "Illustrative baseline",
  statisticalSignificance: "INSUFFICIENT SAMPLE SIZE",
  sampleSizeHonestNote: "0 verified recovery transactions across 4 observed transactions.",
  productionMerchantRecovery: "Not measured",
  strategyBreakdown: [
    {
      strategy: "PAYMENT_LINK",
      sampleSize: 1,
      observedRecoveries: 0,
      observedRecoveryRate: 0.0,
      attributionStatus: "Not enough observations",
    },
    {
      strategy: "REMINDER",
      sampleSize: 0,
      observedRecoveries: 0,
      observedRecoveryRate: 0.0,
      attributionStatus: "No observations",
    },
    {
      strategy: "RETRY",
      sampleSize: 0,
      observedRecoveries: 0,
      observedRecoveryRate: 0.0,
      attributionStatus: "No observations",
    },
    {
      strategy: "STOP",
      sampleSize: 0,
      observedRecoveries: 0,
      observedRecoveryRate: 0.0,
      attributionStatus: "No observations",
    },
  ],
  funnel: [
    { stage: "Failed Payments", count: 1, description: "Raw gateway failure records" },
    { stage: "At-Risk Payments", count: 1, description: "Unresolved drop-offs in active queue" },
    { stage: "Analyzed", count: 1, description: "Evaluated with Gemini 3.6 Flash" },
    { stage: "Policy Approved", count: 0, description: "Passed Guarded Autopilot rules" },
    { stage: "Recovery Action", count: 0, description: "Dispatched intervention execution" },
    { stage: "Recovered", count: 0, description: "Verified captured/paid status" },
  ],
  historicalTrendAvailable: false,
  historicalTrendReason: "Historical trend unavailable: minimum 3 consecutive observation periods required.",
};

test.describe("Phase 5 Outcome Metrics & Scientific Honesty", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { id: "usr_phase5_operator", username: "operator@revenueos.ai", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector("text=REVENUE RADAR", { timeout: 10000 });

    // Inject metrics via WebSocket client
    await page.evaluate(({ metrics }) => {
      const client = (window as unknown as {
        __REVENUE_WS_CLIENT__?: {
          dispatchServerMessage: (msg: unknown) => void;
        };
      }).__REVENUE_WS_CLIENT__;

      if (client) {
        client.dispatchServerMessage({
          protocolVersion: "v1",
          type: "metrics.summary.response",
          timestamp: new Date().toISOString(),
          payload: metrics,
        });
      }
    }, { metrics: testMetricSummary });

    await page.waitForTimeout(300);
  });

  test("1-8. Outcome Metrics view presents truthful data with strict sample size honesty", async ({ page }) => {
    // Navigate to Outcome Metrics tab
    const metricsTabBtn = page.locator("button:has-text('Outcome Metrics')");
    await expect(metricsTabBtn).toBeVisible();
    await metricsTabBtn.click();

    // 1. Header & Primary Metrics
    await expect(page.locator("text=Outcome Metrics — Business Impact with Scientific Honesty")).toBeVisible();
    await expect(page.locator("text=Revenue at Risk").first()).toBeVisible();
    await expect(page.locator("text=Expected Recoverable").first()).toBeVisible();
    await expect(page.locator("text=Actually Recovered").first()).toBeVisible();
    await expect(page.locator("text=Estimated Lift").first()).toBeVisible();
    await expect(page.locator("text=Recovery Rate").first()).toBeVisible();

    // 2. Sample Size Honesty Banner
    const sampleBanner = page.locator("[data-testid='insufficient-sample-banner']");
    await expect(sampleBanner).toBeVisible();
    await expect(sampleBanner).toContainText("INSUFFICIENT SAMPLE SIZE");
    await expect(sampleBanner).toContainText("illustrative baseline");

    // 3. Attribution Status Badge
    const statusBadge = page.locator("[data-testid='attribution-status-badge']");
    await expect(statusBadge).toBeVisible();
    await expect(statusBadge).toContainText("INSUFFICIENT SAMPLE SIZE");

    // 4. Evidence Context Panel
    await expect(page.locator("text=Observed Transactions")).toBeVisible();
    await expect(page.locator("text=Observed Recoveries").first()).toBeVisible();
    await expect(page.locator("text=Illustrative baseline").first()).toBeVisible();

    // 5. Recovery Funnel
    await expect(page.locator("text=Deterministic Recovery Funnel")).toBeVisible();
    await expect(page.locator("text=Failed Payments").first()).toBeVisible();
    await expect(page.locator("text=At-Risk Payments").first()).toBeVisible();
    await expect(page.locator("text=Policy Approved").first()).toBeVisible();

    // 6. Strategy-Level Breakdown Table
    await expect(page.locator("text=Strategy-Level Recovery Breakdown")).toBeVisible();
    await expect(page.locator("td:has-text('PAYMENT_LINK')")).toBeVisible();
    await expect(page.locator("td:has-text('REMINDER')")).toBeVisible();
    await expect(page.locator("td:has-text('RETRY')")).toBeVisible();
    await expect(page.locator("td:has-text('STOP')")).toBeVisible();
    await expect(page.locator("span:has-text('Not enough observations')").first()).toBeVisible();

    // 7. Historical Trend Professional State
    const trendBadge = page.locator("[data-testid='historical-trend-badge']");
    await expect(trendBadge).toBeVisible();
    await expect(trendBadge).toContainText("Historical trend unavailable");

    // 8. Metric Semantics Glossary
    await expect(page.locator("text=Scientific Honesty • Metric Semantics Reference")).toBeVisible();
    await expect(page.locator("text=Statistically Established")).toBeVisible();

    // Zero secret leakage check
    const content = await page.content();
    expect(content).not.toContain("GEMINI_API_KEY");
    expect(content).not.toContain("RAZORPAY_KEY_SECRET");
    expect(content).not.toContain("TURNSTILE_SECRET_KEY");
  });
});
