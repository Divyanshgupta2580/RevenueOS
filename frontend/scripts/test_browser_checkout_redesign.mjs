import { chromium } from "playwright";
import path from "path";

const ARTIFACTS_DIR = "/Users/apple/.gemini/antigravity-ide/brain/65a0b058-4b04-4a9e-8f6b-28bb66fd45cc";

async function run() {
  console.log("Starting End-to-End Authenticated Browser Test for RevenueOS...");

  // 1. Authenticate via backend to obtain a valid session cookie
  const uniqueUser = `op_${Date.now()}@revenueos.local`;
  const password = "StrongPassword2026!";
  const turnstileToken = "1x0000000000000000000000000000000AA"; // Cloudflare official test pass token

  console.log(`Registering test operator: ${uniqueUser}...`);
  const regRes = await fetch("http://localhost:8000/api/auth/register/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: uniqueUser,
      password: password,
      confirmPassword: password,
      turnstileToken: turnstileToken,
    }),
  });

  let sessionCookieValue = "";
  const setCookieHeader = regRes.headers.get("set-cookie");
  if (setCookieHeader) {
    const match = setCookieHeader.match(/revenueos_session=([^;]+)/);
    if (match) sessionCookieValue = match[1];
  }

  if (!sessionCookieValue) {
    // Try login if already registered
    console.log("Trying login...");
    const loginRes = await fetch("http://localhost:8000/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: uniqueUser,
        password: password,
        turnstileToken: turnstileToken,
      }),
    });
    const loginCookie = loginRes.headers.get("set-cookie");
    if (loginCookie) {
      const match = loginCookie.match(/revenueos_session=([^;]+)/);
      if (match) sessionCookieValue = match[1];
    }
  }

  console.log(`Session cookie acquired: ${sessionCookieValue ? "YES (length: " + sessionCookieValue.length + ")" : "NO"}`);

  // 2. Launch Chromium browser
  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  if (sessionCookieValue) {
    await context.addCookies([
      {
        name: "revenueos_session",
        value: sessionCookieValue,
        domain: "localhost",
        path: "/",
        httpOnly: true,
        secure: false,
        sameSite: "Lax",
      },
    ]);
  }

  const page = await context.newPage();

  // Listen to WebSocket events in browser
  page.on("websocket", (ws) => {
    console.log(`[Browser WS] Created: ${ws.url()}`);
    ws.on("framereceived", (event) => {
      try {
        const data = JSON.parse(event.payload);
        console.log(`[Browser WS Frame Received] type: ${data.type}`);
      } catch {
        console.log(`[Browser WS Frame Received] ${event.payload.slice(0, 60)}...`);
      }
    });
    ws.on("framesent", (event) => {
      try {
        const data = JSON.parse(event.payload);
        console.log(`[Browser WS Frame Sent] type: ${data.type}`);
      } catch {
        console.log(`[Browser WS Frame Sent] ${event.payload.slice(0, 60)}...`);
      }
    });
    ws.on("close", () => console.log(`[Browser WS] Closed`));
  });

  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.text().includes("WebSocket")) {
      console.log(`[Browser Console ${msg.type()}]: ${msg.text()}`);
    }
  });

  // 3. Navigate to Dashboard
  console.log("Navigating to http://localhost:3000/...");
  await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);

  // 4. Verify WebSocket status indicator in Header
  const statusBtn = page.locator("button[aria-label^='WebSocket status:']");
  await statusBtn.waitFor({ state: "visible", timeout: 8000 });
  const statusText = await statusBtn.innerText();
  console.log(`WebSocket Status Pill Text: "${statusText.trim()}"`);

  // Hover to trigger tooltip
  await statusBtn.hover();
  await page.waitForTimeout(400);

  const tooltipLocator = page.locator("text=WebSocket connected");
  const tooltipVisible = await tooltipLocator.isVisible().catch(() => false);
  console.log(`Tooltip visible on hover: ${tooltipVisible}`);

  // Capture Dashboard screenshot
  const dashPath = path.join(ARTIFACTS_DIR, "dashboard_websocket_connected.png");
  await page.screenshot({ path: dashPath, fullPage: false });
  console.log(`Captured dashboard screenshot: ${dashPath}`);

  // 5. Navigate to Checkout tab
  console.log("Clicking Checkout navigation tab...");
  await page.locator("button:has-text('Checkout')").click();
  await page.waitForTimeout(1500);

  // 6. Verify Redesigned Checkout Page UI Components
  console.log("Verifying redesigned Checkout UI components...");

  // Section Header
  const headerVisible = await page.locator("text=Secure Payments for Revenue Recovery").isVisible();
  console.log(`- Section Header 'Secure Payments for Revenue Recovery': ${headerVisible}`);

  // Test Mode Card on Right
  const testModeCardVisible = await page.locator("text=You are using Razorpay Test Mode").isVisible();
  console.log(`- Compact Test Mode Card: ${testModeCardVisible}`);

  // 5 KPI Cards
  const kpiAtRisk = await page.getByText("REVENUE AT RISK", { exact: true }).isVisible();
  const kpiExpected = await page.getByText("EXPECTED RECOVERABLE", { exact: true }).isVisible();
  const kpiRecovered = await page.getByText("ACTUALLY RECOVERED", { exact: true }).isVisible();
  const kpiLift = await page.getByText("ESTIMATED LIFT", { exact: true }).isVisible();
  const kpiRate = await page.getByText("RECOVERY RATE", { exact: true }).isVisible();
  console.log(`- 5 KPI Cards present: AtRisk=${kpiAtRisk}, Expected=${kpiExpected}, Recovered=${kpiRecovered}, Lift=${kpiLift}, Rate=${kpiRate}`);

  // Central Razorpay Card
  const centralCardVisible = await page.locator("text=Razorpay Standard Web Checkout").isVisible();
  const hmacBadgeVisible = await page.getByText("HMAC-SHA256", { exact: true }).isVisible();
  const verifiedBadgeVisible = await page.getByText("Verified", { exact: true }).isVisible();
  console.log(`- Central Razorpay Card: ${centralCardVisible}, HMAC-SHA256: ${hmacBadgeVisible}, Verified: ${verifiedBadgeVisible}`);

  // Check if verified state or form state
  const hasSuccessBanner = await page.locator("text=Payment Verified & Captured Successfully!").isVisible().catch(() => false);
  console.log(`- Success banner currently visible: ${hasSuccessBanner}`);

  if (hasSuccessBanner) {
    const verifiedPath = path.join(ARTIFACTS_DIR, "checkout_redesign_verified.png");
    await page.screenshot({ path: verifiedPath, fullPage: true });
    console.log(`Captured verified state screenshot: ${verifiedPath}`);

    // Click "Make Another Payment" to test the interactive checkout form
    console.log("Clicking 'Make Another Payment' CTA...");
    await page.locator("button:has-text('Make Another Payment')").click();
    await page.waitForTimeout(600);

    const formVisible = await page.locator("text=Select Amount (INR)").isVisible();
    console.log(`- Interactive Amount Selector visible: ${formVisible}`);

    const payBtnVisible = await page.locator("button:has-text('with Razorpay')").isVisible();
    console.log(`- Electric Blue Pay Button visible: ${payBtnVisible}`);

    const formPath = path.join(ARTIFACTS_DIR, "checkout_redesign_form.png");
    await page.screenshot({ path: formPath, fullPage: true });
    console.log(`Captured form state screenshot: ${formPath}`);

    // Click "View Last Verified Transaction"
    await page.locator("button:has-text('View Last Verified Transaction')").click();
    await page.waitForTimeout(400);
  } else {
    // If initially in form state
    const formPath = path.join(ARTIFACTS_DIR, "checkout_redesign_form.png");
    await page.screenshot({ path: formPath, fullPage: true });
    console.log(`Captured form state screenshot: ${formPath}`);
  }

  // 7. Test Responsive Viewports
  console.log("Testing responsive viewports...");
  const viewports = [
    { name: "1440px Desktop", width: 1440, height: 900 },
    { name: "1280px Desktop", width: 1280, height: 800 },
    { name: "1024px Tablet Landscape", width: 1024, height: 768 },
    { name: "768px Tablet Portrait", width: 768, height: 1024 },
    { name: "390px Mobile Portrait", width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.waitForTimeout(300);
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log(`- Viewport ${vp.name} (${vp.width}x${vp.height}): Overflow=${hasHorizontalOverflow}`);
    if (vp.width === 390) {
      const mobilePath = path.join(ARTIFACTS_DIR, "checkout_redesign_mobile_390.png");
      await page.screenshot({ path: mobilePath, fullPage: true });
      console.log(`Captured mobile screenshot: ${mobilePath}`);
    }
  }

  // 8. Strict Security Audit: Verify ZERO occurrences of KEY_SECRET
  const htmlContent = await page.content();
  const hasKeySecret = htmlContent.includes("KEY_SECRET");
  console.log(`Security Audit: 'KEY_SECRET' present in rendered HTML: ${hasKeySecret}`);
  if (hasKeySecret) {
    throw new Error("CRITICAL SECURITY ERROR: 'KEY_SECRET' was found in rendered user interface!");
  }

  await browser.close();
  console.log("End-to-End Authenticated Browser Test completed successfully!");
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
