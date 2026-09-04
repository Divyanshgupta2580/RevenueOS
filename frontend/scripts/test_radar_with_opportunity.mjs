/**
 * Test script to verify the 12-column table and the Opportunity Drawer
 * with active opportunity data, and capture high-resolution visual evidence.
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
    createdAt: new Date(Date.now() - 42 * 60 * 1000).toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    paymentId: "pay_P2bC8x5WnJ4t7Y",
    orderId: "order_M4t7Y8x5WnJ",
    customerMasked: "a***@fintech.co",
    amountPaise: 845000,
    currency: "INR",
    status: "failed",
    failureReason: "Issuer bank network timed out during 2FA",
    failureCategory: "network_timeout",
    recoverabilityScore: 92.0,
    expectedRecoveryValuePaise: 777400,
    retryCount: 0,
    maxRetries: 3,
    heuristicRecommendedAction: "RETRY",
    recommendedIntervention: "RETRY",
    aiConfidence: 0.94,
    policyStatus: "APPROVED",
    policyReason: "Transient network failure eligible for immediate deterministic retry attempt.",
    recoveryStatus: "at_risk",
    createdAt: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
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
    createdAt: new Date(Date.now() - 180 * 60 * 1000).toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

async function runTest() {
  console.log("Launching browser to test active Opportunity Table and Drawer...");
  const browser = await chromium.launch({ headless: true });

  // 1. Desktop 1440x900
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

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

  // Inject sample opportunities into page
  await page.addInitScript((opps) => {
    window.__SAMPLE_OPPORTUNITIES__ = opps;
  }, sampleOpportunities);

  await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);

  // Dispatch WebSocket response simulation to state
  await page.evaluate((opps) => {
    if (window.__REVENUE_WS_CLIENT__) {
      window.__REVENUE_WS_CLIENT__.dispatchServerMessage({
        protocolVersion: "v1",
        type: "revenue.list.response",
        timestamp: new Date().toISOString(),
        payload: { opportunities: opps },
      });
    }
  }, sampleOpportunities);

  await page.waitForTimeout(1000);

  // Take screenshot of Desktop Table with 12 columns
  const tableScreenshot = path.join(ARTIFACTS_DIR, "radar_table_active_desktop.png");
  await page.screenshot({ path: tableScreenshot });
  console.log(`Saved 12-column desktop table screenshot: ${tableScreenshot}`);

  // Click Inspect on the first opportunity to open Drawer
  const inspectButton = page.locator("button:has-text('Inspect')").first();
  await inspectButton.click();
  await page.waitForTimeout(600);

  // Capture Opportunity Drawer screenshot
  const drawerScreenshot = path.join(ARTIFACTS_DIR, "radar_opportunity_drawer_active.png");
  await page.screenshot({ path: drawerScreenshot });
  console.log(`Saved opportunity drawer screenshot: ${drawerScreenshot}`);

  await context.close();

  // 2. Mobile 390x844 with active opportunities (card view)
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
  });
  const mobilePage = await mobileContext.newPage();

  await mobilePage.route("**/api/auth/me/", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        user: { username: "operator", role: "operator" },
      }),
    });
  });

  await mobilePage.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await mobilePage.waitForTimeout(500);

  await mobilePage.evaluate((opps) => {
    if (window.__REVENUE_WS_CLIENT__) {
      window.__REVENUE_WS_CLIENT__.dispatchServerMessage({
        protocolVersion: "v1",
        type: "revenue.list.response",
        timestamp: new Date().toISOString(),
        payload: { opportunities: opps },
      });
    }
  }, sampleOpportunities);

  await mobilePage.waitForTimeout(1000);

  const mobileCardsScreenshot = path.join(ARTIFACTS_DIR, "radar_mobile_active_cards.png");
  await mobilePage.screenshot({ path: mobileCardsScreenshot });
  console.log(`Saved mobile active cards screenshot: ${mobileCardsScreenshot}`);

  // Scroll down to cards section on mobile
  await mobilePage.evaluate(() => window.scrollBy(0, 680));
  await mobilePage.waitForTimeout(500);

  const mobileScrolledScreenshot = path.join(ARTIFACTS_DIR, "radar_mobile_scrolled_cards.png");
  await mobilePage.screenshot({ path: mobileScrolledScreenshot });
  console.log(`Saved mobile scrolled cards screenshot: ${mobileScrolledScreenshot}`);

  await mobileContext.close();
  await browser.close();

  console.log("All visual opportunity tests completed successfully!");
}

runTest().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
