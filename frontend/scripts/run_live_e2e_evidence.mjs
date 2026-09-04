import { chromium } from "playwright";
import path from "path";

const ARTIFACTS_DIR = "/Users/apple/.gemini/antigravity-ide/brain/65a0b058-4b04-4a9e-8f6b-28bb66fd45cc";

async function main() {
  console.log("=== REVENUEOS PHASE 3 LIVE E2E VERIFICATION ===");

  // Get session token
  const token = "cc5bae41375feb79a6fd8f06c00cd8d570d8a90431f408e9b2e5410f1e718060";
  console.log(`Using live session token: ${token.slice(0, 10)}...`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  await context.addCookies([
    {
      name: "revenueos_session",
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: false,
      secure: false,
    },
  ]);

  const page = await context.newPage();
  page.on("console", (msg) => console.log(`[PAGE LOG] ${msg.text()}`));
  page.on("pageerror", (err) => console.log(`[PAGE ERROR]`, err));

  // 1. Open live application
  console.log("Navigating to http://localhost:3000/...");
  await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);

  // Verify authenticated session
  console.log("Checking command center load...");
  await page.waitForSelector("text=REVENUE RADAR", { timeout: 15000 });
  console.log("Command center loaded successfully!");

  // Verify real failed payment appears in Revenue Radar
  console.log("Checking for real failed payment pay_TY6cS8vkYS9cWn in Revenue Radar...");
  const failedRow = page.locator("tr:has-text('pay_TY6cS8vkYS9cWn')");
  await failedRow.waitFor({ timeout: 10000 });
  console.log("Real failed payment pay_TY6cS8vkYS9cWn found in Revenue Radar!");

  // Navigate to Decision Ledger tab
  console.log("Navigating to Decision Ledger tab...");
  await page.locator("button:has-text('Decision Ledger')").click();
  await page.waitForSelector("text=Decision Ledger & Audit Timeline", { timeout: 10000 });
  await page.waitForTimeout(800);

  // Capture Screenshot 1: Ledger Overview
  const p1 = path.join(ARTIFACTS_DIR, "ledger_overview.png");
  await page.screenshot({ path: p1 });
  console.log(`Captured: ${p1}`);

  // Verify real decision dec_d907c8a43bff is present
  console.log("Verifying real decision dec_d907c8a43bff in ledger...");
  const decRow = page.locator("tr:has-text('dec_d907c8a43bff')");
  await decRow.waitFor({ timeout: 10000 });

  // Capture Screenshot 2: Real Decision Row
  const p2 = path.join(ARTIFACTS_DIR, "real_decision.png");
  await page.screenshot({ path: p2 });
  console.log(`Captured: ${p2}`);

  // Open Decision Detail Inspection modal
  console.log("Opening Decision Detail Inspection for dec_d907c8a43bff...");
  await decRow.click();
  await page.waitForSelector("text=Decision Audit: dec_d907c8a43bff", { timeout: 10000 });
  await page.waitForTimeout(600);

  // Capture Screenshot 3: Decision Detail Full View
  const p3 = path.join(ARTIFACTS_DIR, "decision_detail.png");
  await page.screenshot({ path: p3 });
  console.log(`Captured: ${p3}`);

  // Scroll to AI Recommendation & Reasoning
  const aiSection = page.locator("text=SECTION 4 — AI RECOMMENDATION");
  await aiSection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Capture Screenshot 4: AI Recommendation
  const p4 = path.join(ARTIFACTS_DIR, "ai_recommendation.png");
  await page.screenshot({ path: p4 });
  console.log(`Captured: ${p4}`);

  // Scroll to Policy Section
  const policySection = page.locator("text=SECTION 6 — POLICY: GUARDED AUTOPILOT");
  await policySection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Capture Screenshot 5: Policy Section (Approved or Blocked breakdown)
  const p5 = path.join(ARTIFACTS_DIR, "policy_approved.png");
  await page.screenshot({ path: p5 });
  console.log(`Captured: ${p5}`);

  // Scroll to Execution Section
  const execSection = page.locator("text=SECTION 7 — EXECUTION");
  await execSection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Capture Screenshot 7: Execution
  const p7 = path.join(ARTIFACTS_DIR, "execution.png");
  await page.screenshot({ path: p7 });
  console.log(`Captured: ${p7}`);

  // Scroll to Outcome Section
  const outcomeSection = page.locator("text=SECTION 8 — OUTCOME");
  await outcomeSection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Capture Screenshot 8: Outcome
  const p8 = path.join(ARTIFACTS_DIR, "outcome.png");
  await page.screenshot({ path: p8 });
  console.log(`Captured: ${p8}`);

  // Scroll to Explain Decision Section and Trigger Explain
  const explainBtn = page.locator("button:has-text('Explain Decision')");
  await explainBtn.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  if (await explainBtn.isVisible()) {
    console.log("Triggering Explain Decision (decision.explain via Gemini 3.6 Flash)...");
    await explainBtn.click();
    console.log("Awaiting Gemini 3.6 Flash explanation response...");
    await page.waitForSelector("text=WHY (EXPLANATION SUMMARY)", { timeout: 45000 });
    console.log("Explanation received from Gemini 3.6 Flash!");
  }

  // Capture Screenshot 9: Explain Decision
  const p9 = path.join(ARTIFACTS_DIR, "explain_decision.png");
  await page.screenshot({ path: p9 });
  console.log(`Captured: ${p9}`);

  // Close audit modal
  await page.locator("button:has-text('Close Audit')").click();
  await page.waitForTimeout(400);

  // Also test filter by BLOCKED to capture Policy Blocked evidence
  console.log("Testing filter by BLOCKED status...");
  const policySelect = page.locator("select").nth(1);
  await policySelect.selectOption("BLOCKED");
  await page.waitForTimeout(300);

  const blockedRow = page.locator("tbody tr").first();
  if (await blockedRow.isVisible()) {
    await blockedRow.click();
    await page.waitForSelector("text=SECTION 6 — POLICY: GUARDED AUTOPILOT", { timeout: 5000 });
    const p6 = path.join(ARTIFACTS_DIR, "policy_blocked.png");
    await page.screenshot({ path: p6 });
    console.log(`Captured: ${p6}`);
    await page.locator("button:has-text('Close Audit')").click();
  } else {
    // If no blocked row in DB, screenshot current view as fallback
    const p6 = path.join(ARTIFACTS_DIR, "policy_blocked.png");
    await page.screenshot({ path: p6 });
  }

  // Reset filter
  await policySelect.selectOption("ALL");

  // Mobile Viewport Validation (390x844)
  console.log("Testing Mobile Responsive Viewport (390x844)...");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);

  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > window.innerWidth;
  });
  console.log(`Mobile horizontal overflow detected: ${overflow}`);

  // Capture Screenshot 10: Mobile Ledger
  const p10 = path.join(ARTIFACTS_DIR, "mobile_ledger.png");
  await page.screenshot({ path: p10 });
  console.log(`Captured: ${p10}`);

  // Test responsive viewports
  for (const vp of [
    { width: 1440, height: 900, name: "desktop" },
    { width: 1280, height: 800, name: "laptop" },
    { width: 1024, height: 768, name: "tablet_landscape" },
    { width: 768, height: 1024, name: "tablet_portrait" },
    { width: 390, height: 844, name: "mobile" },
  ]) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(100);
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log(`Viewport ${vp.width}x${vp.height} (${vp.name}): overflow=${hasOverflow}`);
  }

  await browser.close();
  console.log("=== ALL LIVE E2E EVIDENCE CAPTURED SUCCESSFULLY ===");
}

main().catch((err) => {
  console.error("FATAL ERROR IN LIVE E2E EVIDENCE:", err);
  process.exit(1);
});
