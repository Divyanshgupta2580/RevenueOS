import { test, expect } from "@playwright/test";

const testDecisions = [
  {
    decisionId: "dec_d907c8a43bff",
    paymentId: "pay_TY6cS8vkYS9cWn",
    modelVersion: "gemini-3.6-flash",
    endpoint: "recovery.analyze",
    requestId: "req_dec_d907c8a43bff",
    paymentSnapshot: {
      paymentId: "pay_TY6cS8vkYS9cWn",
      orderId: "order_TY6c9yGjXS0F8G",
      customerId: "cust_vkYS9cWn",
      customerEmail: "operator@revenueos.com",
      amount: 150000,
      currency: "INR",
      status: "failed",
      failureCategory: "soft_decline",
      failureReason: "international_transaction_not_allowed",
      method: "card",
      retryCount: 0,
      maxRetriesAllowed: 3,
      createdAt: "2026-09-04T21:19:54.523000Z",
    },
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹1,500.00",
        currency: "INR",
        failureCategory: "soft_decline",
        failureReason: "international_transaction_not_allowed",
        paymentMethod: "card",
        captured: false,
      },
      backendCalculations: {
        recoverabilityScore: 85,
        expectedRecoveryPaise: 95625,
        formattedERV: "₹956.25",
        estimatedProbability: 0.85,
        paymentAge: "3m ago",
      },
      historicalEvidence: {
        customerId: "op***@revenueos.com",
        customerSuccessfulPayments: 0,
        customerFailedPayments: 1,
        recoveryAttempts: 0,
      },
      policyConstraints: {
        maxRetries: 3,
        cooldownSeconds: 300,
        allowedActions: ["RETRY", "PAYMENT_LINK", "REMINDER", "STOP"],
        maxAmountPaise: 100000000,
      },
      systemState: {
        isTestMode: true,
        duplicateProtectionActive: true,
        paymentLinkApiAvailable: true,
        simulatedRetryAvailable: true,
      },
    },
    aiRecommendation: {
      action: "PAYMENT_LINK",
      confidence: 0.85,
      expectedRecoveryValuePaise: 95625,
      reason:
        "International transaction restriction triggered failure. Providing a payment link allows the customer to switch to an alternative domestic payment method or card.",
      supportingFactors: [
        "High recoverability score of 85/100",
        "PAYMENT_LINK enables alternative domestic payment methods",
        "No previous retry attempts made",
      ],
      riskFactors: [],
      reasoningSummary: "International transaction decline recovery via domestic payment link.",
    },
    policyDecision: {
      status: "APPROVED",
      authorizedAction: "PAYMENT_LINK",
      blockingRule: null,
      blockingReason: null,
      rulesEvaluated: [
        { ruleName: "USER_AUTHORIZATION", passed: true, reason: "User 'operator' authorized with role 'operator'." },
        { ruleName: "SUPPORTED_ACTION", passed: true, reason: "Action 'PAYMENT_LINK' is supported." },
        { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment has eligible status 'failed'." },
        { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity is active." },
        { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount 150000 paise is valid." },
        { ruleName: "RETRY_THRESHOLD", passed: true, reason: "Retry threshold not applicable to action 'PAYMENT_LINK'." },
        { ruleName: "RISK_POLICY", passed: true, reason: "Risk policy checks passed." },
        { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Action is unique." },
      ],
      evaluatedAt: "2026-09-04T21:23:25.838565Z",
    },
    executionStatus: "EXECUTED",
    executionResult: { paymentLinkId: "plink_TY6cTestLink99" },
    executionLatencyMs: 142.5,
    executedAt: "2026-09-04T21:23:26.107000Z",
    outcome: "PENDING",
    outcomeActualPaise: null,
    outcomeAt: null,
    auditTimeline: [
      {
        stage: "FAILURE_DETECTED",
        title: "Payment Failure Ingested",
        status: "DETECTED",
        timestamp: "2026-09-04T21:19:54.523000Z",
        details: { paymentId: "pay_TY6cS8vkYS9cWn", failureCategory: "soft_decline" },
      },
      {
        stage: "CONTEXT_CONSTRUCTED",
        title: "Decision Context Envelope Constructed",
        status: "CONSTRUCTED",
        timestamp: "2026-09-04T21:23:25.838666Z",
        details: { protocolVersion: "1.0", endpoint: "recovery.analyze" },
      },
      {
        stage: "AI_RECOMMENDATION",
        title: "Gemini 3.6 Flash Advisory: PAYMENT_LINK",
        status: "RECOMMENDED",
        timestamp: "2026-09-04T21:23:25.838666Z",
        details: { action: "PAYMENT_LINK", confidence: 0.85, model: "gemini-3.6-flash" },
      },
      {
        stage: "POLICY_EVALUATION",
        title: "Guarded Autopilot Policy Verdict: APPROVED",
        status: "APPROVED",
        timestamp: "2026-09-04T21:23:25.838666Z",
        details: { verdict: "APPROVED", rulesEvaluated: 8 },
      },
    ],
    createdAt: "2026-09-04T21:23:25.838000Z",
  },
  {
    decisionId: "dec_blocked_fraud_99",
    paymentId: "pay_fraud_terminal_01",
    modelVersion: "gemini-3.6-flash",
    endpoint: "recovery.analyze",
    requestId: "req_dec_blocked_01",
    paymentSnapshot: {
      paymentId: "pay_fraud_terminal_01",
      orderId: "order_fraud_01",
      customerId: "cust_fraud_01",
      customerEmail: "fraudster@suspicious.net",
      amount: 4500000,
      currency: "INR",
      status: "failed",
      failureCategory: "lost_stolen_card",
      failureReason: "Card reported lost or stolen by cardholder",
      method: "card",
      retryCount: 3,
      maxRetriesAllowed: 3,
      createdAt: "2026-09-04T20:15:00.000000Z",
    },
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹45,000.00",
        currency: "INR",
        failureCategory: "lost_stolen_card",
        failureReason: "Card reported lost or stolen by cardholder",
      },
    },
    aiRecommendation: {
      action: "STOP",
      confidence: 0.99,
      expectedRecoveryValuePaise: 0,
      reason: "Terminal failure with suspected stolen card and excessive retry count.",
      supportingFactors: ["Category lost_stolen_card is terminal", "Retry count reached maximum"],
      riskFactors: ["Extreme fraud risk"],
      reasoningSummary: "Terminal decline; execution prohibited.",
    },
    policyDecision: {
      status: "BLOCKED",
      authorizedAction: null,
      blockingRule: "RISK_POLICY",
      blockingReason: "Action blocked by risk rule: lost_stolen_card is non-recoverable.",
      rulesEvaluated: [
        { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator authorized." },
        { ruleName: "SUPPORTED_ACTION", passed: true, reason: "Action 'STOP' is supported." },
        { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment status failed is eligible." },
        { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity active." },
        { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount valid." },
        { ruleName: "RETRY_THRESHOLD", passed: false, reason: "Max retries (3) exceeded." },
        { ruleName: "RISK_POLICY", passed: false, reason: "Terminal category: lost_stolen_card." },
        { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Unique." },
      ],
      evaluatedAt: "2026-09-04T20:16:00.000000Z",
    },
    executionStatus: "BLOCKED",
    executionResult: null,
    executionLatencyMs: null,
    executedAt: null,
    outcome: "BLOCKED_BY_POLICY",
    outcomeActualPaise: null,
    outcomeAt: null,
    auditTimeline: [],
    createdAt: "2026-09-04T20:16:00.000000Z",
  },
];

test.describe("Phase 3 Decision Ledger & Audit Proof Layer", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { id: "usr_test_01", username: "operator@revenueos.com", role: "operator" },
        }),
      });
    });

    await page.goto("/");
    await page.waitForSelector("text=REVENUE RADAR", { timeout: 10000 });

    // Inject test decisions and mock RPC handler for decision.explain
    await page.evaluate(({ decs }) => {
      const client = (window as unknown as {
        __REVENUE_WS_CLIENT__?: {
          dispatchServerMessage: (msg: unknown) => void;
          request: (action: string, payload: unknown, timeout?: number) => Promise<unknown>;
        };
      }).__REVENUE_WS_CLIENT__;

      if (client) {
        client.dispatchServerMessage({
          protocolVersion: "v1",
          type: "decision.list.response",
          timestamp: new Date().toISOString(),
          payload: {
            decisions: decs,
            total: decs.length,
          },
        });

        // Mock RPC for decision.explain
        const origReq = client.request.bind(client);
        client.request = async (action: string, payload: unknown, timeout?: number) => {
          if (action === "decision.explain") {
            return {
              protocolVersion: "v1",
              type: "decision.explain.response",
              timestamp: new Date().toISOString(),
              payload: {
                decisionId: (payload as { decisionId?: string })?.decisionId,
                explanation: {
                  decision_id: (payload as { decisionId?: string })?.decisionId,
                  explanation:
                    "International payment failure was authorized for a payment link intervention because recoverability is 85% and no retries have occurred.",
                  key_factors: [
                    "Zero retry count to date",
                    "Recoverability score of 85/100",
                    "Merchant policy permits PAYMENT_LINK for soft declines",
                  ],
                  policy_alignment:
                    "Fully aligned with Guarded Autopilot rules RETRY_THRESHOLD, RISK_POLICY, and SUPPORTED_ACTION.",
                  counterfactual:
                    "If retry count had reached 3 or card was flagged for fraud, policy engine would block execution.",
                  counterfactuals: [
                    "Exceeding retry threshold would trigger block",
                    "Chargeback flag would trigger hard stop",
                  ],
                },
              },
            };
          }
          return origReq(action, payload, timeout);
        };
      }
    }, { decs: testDecisions });

    await page.waitForTimeout(300);
  });

  test("1-18. Complete Decision Ledger audit experience verification", async ({ page }) => {
    // Navigate to Decision Ledger tab
    await page.locator("button:has-text('Decision Ledger')").click();

    // 1. Ledger loads & header renders
    await expect(page.locator("text=Decision Ledger & Audit Timeline")).toBeVisible();
    await expect(
      page.locator("text=Every recovery decision can be traced from payment facts to AI reasoning")
    ).toBeVisible();

    // 2. Real decision rows appear in table
    await expect(page.locator("text=dec_d907c8a43bff")).toBeVisible();
    await expect(page.locator("text=pay_TY6cS8vkYS9cWn")).toBeVisible();
    await expect(page.locator("text=dec_blocked_fraud_99")).toBeVisible();

    // 3. Search and filter controls work (PART M)
    const searchInput = page.locator("input[placeholder*='Search by Decision ID']");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("dec_d907c8a43bff");
    await expect(page.locator("text=dec_d907c8a43bff")).toBeVisible();
    await expect(page.locator("text=dec_blocked_fraud_99")).not.toBeVisible();

    // Clear search
    await searchInput.fill("");
    await expect(page.locator("text=dec_blocked_fraud_99")).toBeVisible();

    // Filter by policy status: BLOCKED
    const policySelect = page.locator("select").nth(1);
    await policySelect.selectOption("BLOCKED");
    await expect(page.locator("text=dec_blocked_fraud_99")).toBeVisible();
    await expect(page.locator("text=dec_d907c8a43bff")).not.toBeVisible();

    // Reset policy filter
    await policySelect.selectOption("ALL");
    await expect(page.locator("text=dec_d907c8a43bff")).toBeVisible();

    // 4. Click row to open Decision Detail Inspection Experience (PART H)
    await page.locator("text=dec_d907c8a43bff").click();

    // Verify Inspection Modal Header & Traceability (PART K)
    await expect(page.locator("text=Decision Audit: dec_d907c8a43bff")).toBeVisible();
    await expect(page.locator("text=req_dec_d907c8a43bff")).toBeVisible();
    await expect(page.locator("text=recovery.analyze")).toBeVisible();

    // SECTION 1 — PAYMENT
    await expect(page.locator("text=SECTION 1 — PAYMENT")).toBeVisible();
    await expect(page.locator("text=order_TY6c9yGjXS0F8G")).toBeVisible();
    await expect(page.locator("text=₹1,500.00").first()).toBeVisible();
    await expect(page.locator("text=soft_decline").first()).toBeVisible();

    // SECTION 2 — VERIFIED FACTS
    await expect(page.locator("text=SECTION 2 — VERIFIED FACTS")).toBeVisible();
    await expect(page.locator("text=VERIFIED FACTS").first()).toBeVisible();

    // SECTION 3 — BACKEND CALCULATIONS
    await expect(page.locator("text=SECTION 3 — BACKEND CALCULATIONS")).toBeVisible();
    await expect(page.locator("text=BACKEND CALCULATED").first()).toBeVisible();
    await expect(page.getByText("85/100", { exact: true })).toBeVisible();
    await expect(page.getByText("₹956.25").first()).toBeVisible();

    // SECTION 4 — AI RECOMMENDATION
    await expect(page.locator("text=SECTION 4 — AI RECOMMENDATION")).toBeVisible();
    await expect(page.locator("text=ADVISORY ONLY • NON-AUTHORIZING")).toBeVisible();
    await expect(page.locator("text=Gemini 3.6 Flash").first()).toBeVisible();

    // SECTION 5 — AI REASONING
    await expect(page.locator("text=SECTION 5 — AI REASONING: WHY?")).toBeVisible();
    await expect(
      page.locator("text=International transaction restriction triggered failure")
    ).toBeVisible();
    await expect(page.locator("text=Supporting Factors:").first()).toBeVisible();

    // SECTION 6 — POLICY: GUARDED AUTOPILOT
    await expect(page.locator("text=SECTION 6 — POLICY: GUARDED AUTOPILOT")).toBeVisible();
    await expect(page.locator("text=AI recommends. Policy authorizes.")).toBeVisible();
    await expect(page.locator("text=POLICY VERDICT: APPROVED")).toBeVisible();

    // Verify all 8 policy rules rendered
    await expect(page.locator("text=USER_AUTHORIZATION").first()).toBeVisible();
    await expect(page.locator("text=SUPPORTED_ACTION").first()).toBeVisible();
    await expect(page.locator("text=PAYMENT_ELIGIBILITY").first()).toBeVisible();
    await expect(page.locator("text=ALREADY_RECOVERED").first()).toBeVisible();
    await expect(page.locator("text=AMOUNT_VALIDITY").first()).toBeVisible();
    await expect(page.locator("text=RETRY_THRESHOLD").first()).toBeVisible();
    await expect(page.locator("text=RISK_POLICY").first()).toBeVisible();
    await expect(page.locator("text=DUPLICATE_EXECUTION").first()).toBeVisible();

    // SECTION 7 — EXECUTION
    await expect(page.locator("text=SECTION 7 — EXECUTION")).toBeVisible();
    await expect(page.locator("span:has-text('EXECUTED')").first()).toBeVisible();

    // SECTION 8 — OUTCOME
    await expect(page.locator("text=SECTION 8 — OUTCOME")).toBeVisible();
    await expect(page.locator("text=OUTCOME PENDING").first()).toBeVisible();

    // PART J — Visual Chronological Audit Timeline
    await expect(page.locator("text=PART J — SEQUENTIAL AUDIT TIMELINE")).toBeVisible();
    await expect(page.locator("text=Payment failure detected")).toBeVisible();
    await expect(page.locator("text=Decision context envelope constructed")).toBeVisible();
    await expect(page.locator("text=Gemini 3.6 Flash recommendation received")).toBeVisible();
    await expect(page.locator("text=Guarded Autopilot policy evaluated")).toBeVisible();

    // PART I — Explain Decision via Gemini 3.6 Flash (decision.explain)
    const explainBtn = page.locator("button:has-text('Explain Decision')");
    await expect(explainBtn).toBeVisible();
    await explainBtn.click();

    // Wait for explanation response
    await expect(page.locator("text=WHY (EXPLANATION SUMMARY)")).toBeVisible();
    await expect(page.locator("text=KEY FACTORS")).toBeVisible();
    await expect(page.locator("text=POLICY ALIGNMENT")).toBeVisible();
    await expect(page.locator("text=COUNTERFACTUAL (WHAT WOULD ALTER THIS DECISION?)")).toBeVisible();

    // Close audit inspection
    await page.locator("button:has-text('Close Audit')").click();
    await expect(page.locator("text=Decision Audit: dec_d907c8a43bff")).not.toBeVisible();

    // Inspect the BLOCKED decision
    await page.locator("text=dec_blocked_fraud_99").click();
    await expect(page.locator("text=Decision Audit: dec_blocked_fraud_99")).toBeVisible();
    await expect(page.locator("text=POLICY VERDICT: BLOCKED")).toBeVisible();
    await expect(page.locator("text=BLOCKING RULE: RISK_POLICY")).toBeVisible();
    await expect(page.locator("text=Terminal category: lost_stolen_card")).toBeVisible();

    // Close blocked inspection
    await page.locator("button:has-text('Close Audit')").click();

    // Mobile Responsive Validation (390x844) & Zero Horizontal Overflow
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator("text=Decision Ledger & Audit Timeline")).toBeVisible();
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // Zero secret exposure in DOM
    const bodyContent = await page.evaluate(() => document.body.innerText);
    expect(bodyContent).not.toContain("rzp_test_secret");
    expect(bodyContent).not.toContain("mongodb+srv");
    expect(bodyContent).not.toContain("AIzaSy");
  });
});
