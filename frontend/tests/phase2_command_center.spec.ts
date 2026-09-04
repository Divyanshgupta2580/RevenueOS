import { test, expect } from "@playwright/test";

const testOpportunities = [
  {
    paymentId: "pay_e2e_approved_001",
    orderId: "order_e2e_app_01",
    customerMasked: "a***@company.io",
    amountPaise: 185000,
    currency: "INR",
    status: "failed",
    failureReason: "Payment authorization timed out at issuer gateway",
    failureCategory: "timeout",
    recoverabilityScore: 82.0,
    expectedRecoveryValuePaise: 151700,
    retryCount: 1,
    maxRetries: 3,
    heuristicRecommendedAction: "PAYMENT_LINK",
    recommendedIntervention: "PAYMENT_LINK",
    aiConfidence: 0.88,
    policyStatus: "APPROVED",
    policyReason: "Failure category permits bounded payment link recovery within retry ceiling.",
    recoveryStatus: "at_risk",
    decisionId: "dec_e2e_app_1234",
    rulesEvaluated: [
      { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator session authorized" },
      { ruleName: "SUPPORTED_ACTION", passed: true, reason: "PAYMENT_LINK in supported set" },
      { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment status failed is eligible" },
      { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity active and unrecovered" },
      { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount 185000 paise within safety bounds" },
      { ruleName: "RETRY_THRESHOLD", passed: true, reason: "Retry count 1 of 3 within limits" },
      { ruleName: "RISK_POLICY", passed: true, reason: "Non-terminal decline permits recovery" },
      { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Idempotency key unique" },
    ],
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹1,850.00",
        currency: "INR",
        failureCategory: "timeout",
        failureReason: "Payment authorization timed out at issuer gateway",
        paymentMethod: "Card (Standard Checkout)",
        captured: false,
      },
      backendCalculations: {
        recoverabilityScore: 82,
        expectedRecoveryPaise: 151700,
        formattedERV: "₹1,517.00",
        estimatedProbability: 0.82,
        paymentAge: "12m ago",
      },
      historicalEvidence: {
        customerId: "a***@company.io",
        customerSuccessfulPayments: 3,
        customerFailedPayments: 1,
        recoveryAttempts: 1,
      },
      policyConstraints: {
        maxRetries: 3,
        cooldownSeconds: 300,
        allowedActions: ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
        maxAmountPaise: 100_000_000,
      },
      systemState: {
        isTestMode: true,
        duplicateProtectionActive: true,
        paymentLinkApiAvailable: true,
        simulatedRetryAvailable: true,
      },
    },
  },
  {
    paymentId: "pay_e2e_blocked_002",
    orderId: "order_e2e_blk_02",
    customerMasked: "f***@suspicious.net",
    amountPaise: 4500000,
    currency: "INR",
    status: "failed",
    failureReason: "Stolen card reported by acquiring bank network",
    failureCategory: "lost_stolen_card",
    recoverabilityScore: 10.0,
    expectedRecoveryValuePaise: 450000,
    retryCount: 3,
    maxRetries: 3,
    heuristicRecommendedAction: "STOP",
    recommendedIntervention: "STOP",
    aiConfidence: 0.99,
    policyStatus: "BLOCKED",
    policyReason: "Hard decline / fraud rule violation. Autopilot blocks all retries.",
    recoveryStatus: "blocked",
    decisionId: "dec_e2e_blk_5678",
    rulesEvaluated: [
      { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator session authorized" },
      { ruleName: "SUPPORTED_ACTION", passed: true, reason: "STOP in supported set" },
      { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment status failed is eligible" },
      { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity active and unrecovered" },
      { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount within bounds" },
      { ruleName: "RETRY_THRESHOLD", passed: false, reason: "Maximum retry limit (3) exceeded" },
      { ruleName: "RISK_POLICY", passed: false, reason: "Category lost_stolen_card is terminal/fraud" },
      { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Unique request" },
    ],
  },
];

const testDecisions = [
  {
    decisionId: "dec_e2e_app_1234",
    paymentId: "pay_e2e_approved_001",
    modelVersion: "gemini-3.6-flash",
    aiRecommendation: {
      action: "PAYMENT_LINK",
      confidence: 0.88,
      expectedRecoveryValuePaise: 151700,
      reason: "Timeout failure has high probability of successful completion via fresh payment link.",
      supportingFactors: [
        "Authentication timeout rather than financial insufficiency",
        "High historical customer success rate",
      ],
      riskFactors: [],
      reasoningSummary: "Omnichannel payment link provides low-friction customer checkout.",
    },
    policyDecision: {
      isApproved: true,
      allowedAction: "PAYMENT_LINK",
      blockingRule: null,
      blockingReason: null,
      rulesEvaluated: testOpportunities[0].rulesEvaluated,
      evaluatedAt: new Date().toISOString(),
    },
    createdAt: new Date().toISOString(),
  },
];

test.describe("Phase 2 Opportunity Intelligence & AI Decision Command Center", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { id: "usr_test_01", username: "operator@revenueos.ai", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector("text=REVENUE RADAR", { timeout: 10000 });

    // Inject test opportunities and mock RPC handlers
    await page.evaluate(({ opps, decs }) => {
      const client = (window as unknown as { __REVENUE_WS_CLIENT__?: { dispatchServerMessage: (msg: unknown) => void; request: (action: string, payload: unknown, timeout?: number) => Promise<unknown> } }).__REVENUE_WS_CLIENT__;
      if (client) {
        client.dispatchServerMessage({
          protocolVersion: "v1",
          type: "revenue.list.response",
          timestamp: new Date().toISOString(),
          payload: {
            opportunities: opps,
            summary: {
              totalOpportunities: opps.length,
              revenueAtRiskPaise: opps.reduce((s: number, o: { amountPaise: number }) => s + o.amountPaise, 0),
              expectedRecoverablePaise: opps.reduce((s: number, o: { expectedRecoveryValuePaise: number }) => s + o.expectedRecoveryValuePaise, 0),
              averageRecoverabilityScore: 82,
            },
          },
        });

        client.dispatchServerMessage({
          protocolVersion: "v1",
          type: "decision.list.response",
          timestamp: new Date().toISOString(),
          payload: {
            decisions: decs,
            total: decs.length,
          },
        });

        // Mock request for decision.explain
        const origReq = client.request.bind(client);
        client.request = async (action: string, payload: unknown, timeout?: number) => {
          if (action === "decision.explain") {
            return {
              protocolVersion: "v1",
              type: "decision.explain.response",
              timestamp: new Date().toISOString(),
              payload: {
                explanation: {
                  summary: "Decision grounded in verified issuer timeout telemetry. Gemini 3.6 Flash recommends PAYMENT_LINK.",
                  decisionFactors: [
                    "Transient network timeout",
                    "Customer transaction history is verified",
                  ],
                  policyAlignment: "Guarded Autopilot approved: all 8 deterministic guardrails satisfied.",
                  counterfactuals: [
                    "If customer was on fraud blacklist, policy would enforce hard STOP.",
                  ],
                },
              },
            };
          }
          return origReq(action, payload, timeout);
        };
      }
    }, { opps: testOpportunities, decs: testDecisions });

    await page.waitForTimeout(400);
  });

  test("1-11. Drawer opens and renders verified facts, recoverability, expected recovery, AI recommendation, and decision evidence", async ({ page }) => {
    // Open Approved Opportunity
    const inspectBtn = page.locator("tr:has-text('pay_e2e_approved_001') button:has-text('Inspect')");
    await inspectBtn.click({ force: true });
    await expect(page.locator("text=REVENUE RECOVERY OPPORTUNITY")).toBeVisible();

    // 1. Payment ID & copy control
    const dialog = page.locator("[role='dialog']");
    await expect(dialog.getByText("pay_e2e_approved_001")).toBeVisible();
    await expect(dialog.getByText("a***@company.io")).toBeVisible();

    // 2. Amount at risk (Strongest financial emphasis)
    await expect(dialog.getByText("₹1,850.00").first()).toBeVisible();

    // 3. Verified Payment Facts
    await expect(dialog.getByText("VERIFIED PAYMENT FACTS")).toBeVisible();
    await expect(dialog.getByText("Gateway Records • Non-Inferred")).toBeVisible();
    await expect(dialog.getByText("Card (Standard Checkout)").first()).toBeVisible();
    await expect(dialog.getByText("1 of 3 used")).toBeVisible();

    // 4. Deterministic Recoverability
    await expect(dialog.getByText("DETERMINISTIC SCORE")).toBeVisible();
    await expect(dialog.getByText("Not an AI score")).toBeVisible();
    await expect(dialog.getByText(/82\s*\/\s*100/).first()).toBeVisible();

    // 5. Backend Calculated Expected Recovery
    await expect(dialog.getByText("EXPECTED RECOVERY")).toBeVisible();
    await expect(dialog.getByText("BACKEND CALCULATED")).toBeVisible();
    await expect(dialog.getByText("₹1,517.00")).toBeVisible();
    await expect(dialog.getByText("Recovery probability: 82%")).toBeVisible();

    // 6. AI Recommendation
    await expect(dialog.getByText("AI RECOMMENDATION (GEMINI 3.6 FLASH)")).toBeVisible();
    await expect(dialog.getByText("ADVISORY ONLY • NON-AUTHORIZING")).toBeVisible();
    await expect(dialog.getByText("PAYMENT LINK").first()).toBeVisible();
    await expect(dialog.getByText("88%")).toBeVisible();

    // 7. Expand Decision Evidence (5 groups)
    await page.$eval("#decision-evidence-toggle", (el) => (el as HTMLElement).click());
    await expect(dialog.getByText("1. VERIFIED FACTS")).toBeVisible();
    await expect(dialog.getByText("2. BACKEND CALCULATIONS")).toBeVisible();
    await expect(dialog.getByText("3. HISTORICAL EVIDENCE")).toBeVisible();
    await expect(dialog.getByText("4. POLICY CONSTRAINTS")).toBeVisible();
    await expect(dialog.getByText("5. SYSTEM STATE")).toBeVisible();
  });

  test("12-16. Policy gate evaluates 8 rules, displays approved execution and blocks forbidden executions", async ({ page }) => {
    // Open Approved Opportunity
    const inspectBtn = page.locator("tr:has-text('pay_e2e_approved_001') button:has-text('Inspect')");
    await inspectBtn.click({ force: true });

    // Policy Gate Section
    await expect(page.locator("text=GUARDED AUTOPILOT")).toBeVisible();
    await expect(page.locator("text=Deterministic Rules Authorize")).toBeVisible();
    await expect(page.locator("#policy-gate-section").getByText("APPROVED")).toBeVisible();

    // 8 Rules evaluated
    await expect(page.locator("text=USER AUTHORIZATION")).toBeVisible();
    await expect(page.locator("text=SUPPORTED ACTION")).toBeVisible();
    await expect(page.locator("text=PAYMENT ELIGIBILITY")).toBeVisible();
    await expect(page.locator("text=ALREADY RECOVERED")).toBeVisible();
    await expect(page.locator("text=AMOUNT VALIDITY")).toBeVisible();
    await expect(page.locator("text=RETRY THRESHOLD")).toBeVisible();
    await expect(page.locator("text=RISK POLICY")).toBeVisible();
    await expect(page.locator("text=DUPLICATE EXECUTION")).toBeVisible();

    // Authorize & Execute button enabled
    const execBtn = page.locator("button:has-text('Authorize & Execute Recovery')");
    await expect(execBtn).toBeVisible();
    await expect(execBtn).toBeEnabled();

    // Close and open blocked opportunity
    await page.locator("button[aria-label='Close command center']").click({ force: true });
    await page.waitForTimeout(300);

    const inspectBlockedBtn = page.locator("tr:has-text('pay_e2e_blocked_002') button:has-text('Inspect')");
    await inspectBlockedBtn.click({ force: true });

    // Policy Gate must show BLOCKED
    await expect(page.locator("#policy-gate-section").getByText("BLOCKED")).toBeVisible();
    await expect(page.locator("text=RECOVERY BLOCKED — RISK_POLICY")).toBeVisible();
  });

  test("17-19. Decision ledger integration, AI explanation trigger, and navigation", async ({ page }) => {
    const inspectBtn = page.locator("tr:has-text('pay_e2e_approved_001') button:has-text('Inspect')");
    await inspectBtn.click({ force: true });

    // Decision Ledger Record section
    await expect(page.locator("text=DECISION LEDGER RECORD")).toBeVisible();
    await expect(page.locator("text=dec_e2e_app_1234")).toBeVisible();

    // Trigger AI Explanation
    const explainBtn = page.locator("#explain-decision-btn");
    await explainBtn.click({ force: true });
    await expect(page.locator("text=AI-GENERATED EXPLANATION (GEMINI 3.6 FLASH)")).toBeVisible();
    await expect(page.locator("text=Transient network timeout")).toBeVisible();

    // View in Ledger link navigates to ledger tab
    const viewLedgerBtn = page.locator("button:has-text('View in Ledger')");
    await viewLedgerBtn.click({ force: true });
    // Drawer closes and Ledger tab active
    await expect(page.locator("h2:has-text('Decision Ledger')")).toBeVisible();
  });

  test("20-23. Zero secret exposure, mobile responsive viewport with zero horizontal overflow", async ({ page }) => {
    // Check DOM for secrets
    const pageContent = await page.content();
    expect(pageContent).not.toContain("GEMINI_API_KEY");
    expect(pageContent).not.toContain("RAZORPAY_KEY_SECRET");
    expect(pageContent).not.toContain("MONGODB_URI");
    expect(pageContent).not.toContain("DJANGO_SECRET_KEY");

    // Open drawer at mobile viewport (390x844)
    await page.setViewportSize({ width: 390, height: 844 });
    const inspectBtn = page.locator("button:has-text('Inspect Opportunity')").first();
    await inspectBtn.click({ force: true });
    await page.waitForTimeout(300);

    // Measure horizontal overflow in dialog
    const overflow = await page.evaluate(() => {
      const el = document.querySelector("[role='dialog'] > div");
      return el ? el.scrollWidth - el.clientWidth : 0;
    });
    expect(overflow).toBe(0);
  });
});
