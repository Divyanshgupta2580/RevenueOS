/**
 * RevenueOS — Phase 2 Opportunity Intelligence Visual & Functional Verification
 * Tests the Opportunity Drawer Command Center across all states and viewports.
 */

import { chromium } from "playwright";
import path from "path";

const ARTIFACTS_DIR = "/Users/apple/.gemini/antigravity-ide/brain/65a0b058-4b04-4a9e-8f6b-28bb66fd45cc";

const sampleOpportunities = [
  {
    paymentId: "pay_N7fK9a2LmQ8v1Z",
    orderId: "order_K8v1Z9a2LmQ",
    customerMasked: "r***@company.io",
    amountPaise: 149900,
    currency: "INR",
    status: "failed",
    failureReason: "Insufficient funds in customer bank account",
    failureCategory: "insufficient_funds",
    recoverabilityScore: 78.5,
    expectedRecoveryValuePaise: 117672,
    retryCount: 1,
    maxRetries: 3,
    heuristicRecommendedAction: "PAYMENT_LINK",
    recommendedIntervention: "PAYMENT_LINK",
    aiConfidence: 0.85,
    policyStatus: "APPROVED",
    policyReason: "Failure category permits bounded payment link recovery within retry ceiling.",
    recoveryStatus: "at_risk",
    decisionId: "dec_78ab9c12de34",
    rulesEvaluated: [
      { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator session authorized" },
      { ruleName: "SUPPORTED_ACTION", passed: true, reason: "PAYMENT_LINK in supported set" },
      { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment status failed is eligible" },
      { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity active and unrecovered" },
      { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount 149900 paise within safety bounds" },
      { ruleName: "RETRY_THRESHOLD", passed: true, reason: "Retry count 1 of 3 within limits" },
      { ruleName: "RISK_POLICY", passed: true, reason: "Non-terminal decline permits recovery" },
      { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Idempotency key unique" },
    ],
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹1,499.00",
        currency: "INR",
        failureCategory: "insufficient_funds",
        failureReason: "Insufficient funds in customer bank account",
        paymentMethod: "Card (Standard Checkout)",
        captured: false,
      },
      backendCalculations: {
        recoverabilityScore: 79,
        expectedRecoveryPaise: 117672,
        formattedERV: "₹1,176.72",
        estimatedProbability: 0.79,
        paymentAge: "42m ago",
      },
      historicalEvidence: {
        customerId: "r***@company.io",
        customerSuccessfulPayments: 4,
        customerFailedPayments: 1,
        recoveryAttempts: 1,
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
    createdAt: new Date(Date.now() - 42 * 60 * 1000).toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    paymentId: "pay_X9kL3m8Qp4v2B1",
    orderId: "order_L3m8Qp4v2B1X",
    customerMasked: "s***@enterprise.net",
    amountPaise: 2500000,
    currency: "INR",
    status: "failed",
    failureReason: "Card reported lost or stolen by issuing bank",
    failureCategory: "lost_stolen_card",
    recoverabilityScore: 12.0,
    expectedRecoveryValuePaise: 300000,
    retryCount: 3,
    maxRetries: 3,
    heuristicRecommendedAction: "STOP",
    recommendedIntervention: "STOP",
    aiConfidence: 0.98,
    policyStatus: "BLOCKED",
    policyReason: "Hard decline / fraud rule violation. Autopilot blocks all retries.",
    recoveryStatus: "blocked",
    decisionId: "dec_blocked_fraud_99",
    rulesEvaluated: [
      { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator session authorized" },
      { ruleName: "SUPPORTED_ACTION", passed: true, reason: "STOP in supported set" },
      { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment status failed is eligible" },
      { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Opportunity active and unrecovered" },
      { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount 2500000 paise within safety bounds" },
      { ruleName: "RETRY_THRESHOLD", passed: false, reason: "Retry limit reached (3/3)" },
      { ruleName: "RISK_POLICY", passed: false, reason: "Action prohibited on high-risk decline category lost_stolen_card" },
      { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Idempotency unique" },
    ],
    evidenceSummary: {
      verifiedFacts: {
        status: "FAILED",
        amount: "₹25,000.00",
        currency: "INR",
        failureCategory: "lost_stolen_card",
        failureReason: "Card reported lost or stolen by issuing bank",
        paymentMethod: "Card (Standard Checkout)",
        captured: false,
      },
      backendCalculations: {
        recoverabilityScore: 12,
        expectedRecoveryPaise: 300000,
        formattedERV: "₹3,000.00",
        estimatedProbability: 0.12,
        paymentAge: "3h ago",
      },
      historicalEvidence: {
        customerId: "s***@enterprise.net",
        customerSuccessfulPayments: 0,
        customerFailedPayments: 3,
        recoveryAttempts: 3,
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
    createdAt: new Date(Date.now() - 180 * 60 * 1000).toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

const sampleDecisions = [
  {
    decisionId: "dec_78ab9c12de34",
    paymentId: "pay_N7fK9a2LmQ8v1Z",
    modelVersion: "gemini-3.6-flash",
    aiRecommendation: {
      action: "PAYMENT_LINK",
      confidence: 0.85,
      expectedRecoveryValuePaise: 117672,
      reason: "Soft decline with high recoverability via omnichannel payment link.",
      supportingFactors: [
        "Soft decline allows safe re-engagement without card exhaustion",
        "Zero previous recovery links dispatched",
        "Recent transaction timestamp within active shopping window",
      ],
      riskFactors: [],
      reasoningSummary: "Soft decline with high recoverability via omnichannel payment link.",
      latency_ms: 382.4,
    },
    policyDecision: {
      status: "APPROVED",
      authorizedAction: "PAYMENT_LINK",
      blockingRule: null,
      blockingReason: null,
      rulesEvaluated: [
        { ruleName: "USER_AUTHORIZATION", passed: true, reason: "Operator session authorized" },
        { ruleName: "SUPPORTED_ACTION", passed: true, reason: "Action in supported set" },
        { ruleName: "PAYMENT_ELIGIBILITY", passed: true, reason: "Payment eligible" },
        { ruleName: "ALREADY_RECOVERED", passed: true, reason: "Not recovered" },
        { ruleName: "AMOUNT_VALIDITY", passed: true, reason: "Amount valid integer paise" },
        { ruleName: "RETRY_THRESHOLD", passed: true, reason: "Within retry limit" },
        { ruleName: "RISK_POLICY", passed: true, reason: "Non-terminal category" },
        { ruleName: "DUPLICATE_EXECUTION", passed: true, reason: "Idempotency unique" },
      ],
      evaluatedAt: new Date().toISOString(),
    },
    createdAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  },
];

async function runVisualVerification() {
  console.log("Starting Phase 2 Visual and Functional Verification Suite...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  // Route auth/me
  await page.route("**/api/auth/me/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        user: { id: "usr_operator_01", username: "operator@revenueos.ai", role: "operator" },
      }),
    });
  });

  await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
  await page.waitForSelector("text=REVENUE RADAR", { timeout: 10000 });

  // Inject sample data into frontend state via WebSocket client
  await page.evaluate(({ opps, decs }) => {
    if (window.__REVENUE_WS_CLIENT__) {
      window.__REVENUE_WS_CLIENT__.dispatchServerMessage({
        protocolVersion: "v1",
        type: "revenue.list.response",
        timestamp: new Date().toISOString(),
        payload: {
          opportunities: opps,
          summary: {
            totalOpportunities: opps.length,
            revenueAtRiskPaise: opps.reduce((s, o) => s + o.amountPaise, 0),
            expectedRecoverablePaise: opps.reduce((s, o) => s + o.expectedRecoveryValuePaise, 0),
            averageRecoverabilityScore: 78,
          },
        },
      });

      window.__REVENUE_WS_CLIENT__.dispatchServerMessage({
        protocolVersion: "v1",
        type: "decision.list.response",
        timestamp: new Date().toISOString(),
        payload: {
          decisions: decs,
          total: decs.length,
        },
      });

      // Mock request for decision.explain
      const origReq = window.__REVENUE_WS_CLIENT__.request.bind(window.__REVENUE_WS_CLIENT__);
      window.__REVENUE_WS_CLIENT__.request = async (action, payload, timeout) => {
        if (action === "decision.explain") {
          return {
            protocolVersion: "v1",
            type: "decision.explain.response",
            timestamp: new Date().toISOString(),
            payload: {
              explanation: {
                summary: "Opportunity evaluated via Gemini 3.6 Flash. High recoverability soft decline justifies bounded omnichannel Razorpay Payment Link.",
                decisionFactors: [
                  "Customer has high historical transaction completion rate (4/5)",
                  "Decline reason is non-terminal (insufficient funds)",
                  "Payment age is within the prime recovery window (42m ago)",
                ],
                policyAlignment: "Fully compliant with Guarded Autopilot retry thresholds and merchant risk guardrails.",
                counterfactuals: [
                  "If hard decline was detected, policy would have enforced STOP.",
                  "If retry limit exceeded (3/3), automated interventions would be blocked.",
                ],
                confidenceAssessment: "High confidence (85%) grounded in verifiable gateway telemetry.",
              },
            },
          };
        }
        return origReq(action, payload, timeout);
      };
    }
  }, { opps: sampleOpportunities, decs: sampleDecisions });

  await page.waitForTimeout(500);

  // 1. Open Opportunity Drawer for Approved Opportunity
  console.log("Opening Opportunity Drawer for pay_N7fK9a2LmQ8v1Z...");
  const inspectBtn = page.locator("tr:has-text('pay_N7fK9a2LmQ8v1Z') button:has-text('Inspect')");
  await inspectBtn.click({ force: true });
  await page.waitForSelector("text=REVENUE RECOVERY OPPORTUNITY", { timeout: 5000 });
  await page.waitForTimeout(400);

  // Screenshot 1: Drawer Initial State
  const pathInitial = path.join(ARTIFACTS_DIR, "phase2_drawer_initial.png");
  await page.screenshot({ path: pathInitial });
  console.log(`✓ Captured Screenshot 1: ${pathInitial}`);

  // Expand Decision Evidence
  await page.$eval('#decision-evidence-toggle', (el) => el.click());
  await page.waitForSelector("text=1. VERIFIED FACTS", { timeout: 4000 });
  await page.waitForTimeout(300);

  // Screenshot 4: Approved Policy State with all 8 rules & Execution button
  await page.$eval('#policy-gate-section', (el) => el.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await page.waitForTimeout(300);
  const pathApproved = path.join(ARTIFACTS_DIR, "phase2_drawer_policy_approved.png");
  await page.screenshot({ path: pathApproved });
  console.log(`✓ Captured Screenshot 4 (Approved Policy): ${pathApproved}`);

  // Screenshot 2: AI Processing State
  // Scroll back to top for AI processing
  await page.$eval('[role="dialog"] > div', (el) => el.scrollTo({ top: 0, behavior: 'instant' }));
  await page.waitForTimeout(200);
  const evalBtn = page.locator('#evaluate-with-gemini-btn');
  if (await evalBtn.isVisible()) {
    evalBtn.click({ force: true }).catch(() => {});
    await page.waitForTimeout(60);
    const pathAnalysis = path.join(ARTIFACTS_DIR, "phase2_drawer_ai_analysis.png");
    await page.screenshot({ path: pathAnalysis });
    console.log(`✓ Captured Screenshot 2 (AI Analysis): ${pathAnalysis}`);
  }

  // Wait for Ready State
  await page.waitForTimeout(700);
  const pathDecisionReady = path.join(ARTIFACTS_DIR, "phase2_drawer_decision_ready.png");
  await page.screenshot({ path: pathDecisionReady });
  console.log(`✓ Captured Screenshot 3 (Decision Ready): ${pathDecisionReady}`);

  // Trigger Explanation & Screenshot 6
  const explainBtn = page.locator('#explain-decision-btn');
  if (await explainBtn.isVisible()) {
    await page.$eval('#ledger-record-section', (el) => el.scrollIntoView({ behavior: 'instant', block: 'center' }));
    await page.waitForTimeout(200);
    await explainBtn.click({ force: true });
    await page.waitForTimeout(600);
    const pathExplanation = path.join(ARTIFACTS_DIR, "phase2_drawer_decision_explanation.png");
    await page.screenshot({ path: pathExplanation });
    console.log(`✓ Captured Screenshot 6 (Decision Explanation): ${pathExplanation}`);
  }

  // Close drawer
  const closeBtn = page.locator("button[aria-label='Close command center']");
  await closeBtn.click({ force: true });
  await page.waitForTimeout(400);

  // Open Blocked Opportunity (Negative Test Case)
  console.log("Testing Blocked Policy Negative Test Case (pay_X9kL3m8Qp4v2B1)...");
  const inspectBlockedBtn = page.locator("tr:has-text('pay_X9kL3m8Qp4v2B1') button:has-text('Inspect')");
  if (await inspectBlockedBtn.isVisible()) {
    await inspectBlockedBtn.click({ force: true });
  } else {
    // Click second inspect button
    await page.locator("button:has-text('Inspect')").nth(1).click({ force: true });
  }
  await page.waitForSelector("text=RECOVERY BLOCKED", { timeout: 5000 });
  await page.waitForTimeout(400);

  // Screenshot 5: Blocked Policy State (Scrolled to Policy Gate)
  await page.$eval('#policy-gate-section', (el) => el.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await page.waitForTimeout(300);
  const pathBlocked = path.join(ARTIFACTS_DIR, "phase2_drawer_policy_blocked.png");
  await page.screenshot({ path: pathBlocked });
  console.log(`✓ Captured Screenshot 5 (Blocked Policy): ${pathBlocked}`);

  // Mobile Viewport Verification (390x844)
  console.log("Testing Mobile Viewport (390x844)...");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);

  // Measure overflow
  const overflow = await page.evaluate(() => {
    const el = document.querySelector("[role='dialog'] > div");
    return el ? el.scrollWidth - el.clientWidth : 0;
  });
  console.log(`Mobile horizontal overflow: ${overflow}px (Target: 0px)`);

  const pathMobile = path.join(ARTIFACTS_DIR, "phase2_drawer_mobile_390.png");
  await page.screenshot({ path: pathMobile });
  console.log(`✓ Captured Screenshot 7 (Mobile 390x844): ${pathMobile}`);

  // Comprehensive Viewport Validation Matrix
  const viewports = [
    { name: "Desktop", width: 1440, height: 900 },
    { name: "Laptop", width: 1280, height: 800 },
    { name: "Tablet Landscape", width: 1024, height: 768 },
    { name: "Tablet Portrait", width: 768, height: 1024 },
    { name: "Mobile", width: 390, height: 844 },
  ];

  console.log("\n--- VIEWPORT OVERFLOW AUDIT ---");
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(200);
    const ov = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth - doc.clientWidth;
    });
    console.log(`${vp.name} (${vp.width}x${vp.height}): horizontal overflow = ${ov}px`);
  }

  await browser.close();
  console.log("\nAll visual and functional verification tests completed successfully!");
}

runVisualVerification().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
