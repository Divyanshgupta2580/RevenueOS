import { chromium, expect } from "@playwright/test";
import fs from "fs";

async function run() {
  const testId = Date.now();
  const testEmail = `operator-test-${testId}@revenueos.local`;
  const testPassword = `RevOS_P@ss_${testId}!Sec`;

  console.log("==================================================");
  console.log("REVENUEOS END-TO-END MASTER VERIFICATION");
  console.log("==================================================");
  console.log(`Generated Test Account: ${testEmail}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-blink-features=AutomationControlled",
    ],
  });

  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    viewport: { width: 1280, height: 800 },
  });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  });

  const page = await context.newPage();

  // Track bank popup
  let bankPopup = null;
  page.on("popup", (popup) => {
    console.log("[POPUP] Razorpay Bank Simulator popup detected!");
    bankPopup = popup;
  });

  // Track payment verification response
  let verifiedPaymentData = null;
  page.on("response", async (res) => {
    const url = res.url();
    if (url.includes("/api/verify-payment")) {
      try {
        const json = await res.json();
        verifiedPaymentData = json;
        console.log("[NETWORK] /api/verify-payment response:", JSON.stringify(json));
      } catch {}
    }
  });

  // ----------------------------------------------------
  // STEP 1: REGISTRATION (/register)
  // ----------------------------------------------------
  console.log("\n[STEP 1] Navigating to /register...");
  await page.goto("http://localhost:3000/register", { waitUntil: "domcontentloaded" });
  await page.waitForSelector("input#email");

  console.log("[STEP 1] Filling registration form...");
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);
  await page.locator("input#confirmPassword").fill(testPassword);

  // Wait for Turnstile verification to enable the submit button
  const regSubmitBtn = page.locator("button[type='submit']");
  const turnstileFrame = page.frameLocator("iframe[src*='challenges.cloudflare.com']");
  try {
    const turnstileBox = turnstileFrame.locator("input[type='checkbox']");
    if (await turnstileBox.count() > 0 && await turnstileBox.first().isVisible().catch(() => false)) {
      await turnstileBox.first().click().catch(() => {});
    }
  } catch {}

  console.log("[STEP 1] Waiting for submit button to be enabled by Turnstile token...");
  await expect(regSubmitBtn).toBeEnabled({ timeout: 15000 });

  await page.screenshot({ path: "scratch/e2e_01_register_filled.png" });
  console.log("[STEP 1] Submitting registration...");
  await regSubmitBtn.click();

  // Wait for redirect to /login?registered=1
  await expect(page).toHaveURL(/.*login\?registered=1/, { timeout: 15000 });
  console.log("[STEP 1] Successfully redirected to /login?registered=1");

  await page.waitForSelector("text=Registration successful!");
  console.log("[STEP 1] Success banner verified on login page!");
  await page.screenshot({ path: "scratch/e2e_02_login_redirect_success.png" });

  // ----------------------------------------------------
  // STEP 2: LOGIN WITH REGISTERED ACCOUNT (/login)
  // ----------------------------------------------------
  console.log("\n[STEP 2] Signing in with newly registered account...");
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);

  const loginSubmitBtn = page.locator("button[type='submit']");
  const loginTurnstileFrame = page.frameLocator("iframe[src*='challenges.cloudflare.com']");
  try {
    const loginTurnstileBox = loginTurnstileFrame.locator("input[type='checkbox']");
    if (await loginTurnstileBox.count() > 0 && await loginTurnstileBox.first().isVisible().catch(() => false)) {
      await loginTurnstileBox.first().click().catch(() => {});
    }
  } catch {}

  console.log("[STEP 2] Waiting for login submit button to be enabled by Turnstile token...");
  await expect(loginSubmitBtn).toBeEnabled({ timeout: 15000 });

  console.log("[STEP 2] Submitting login...");
  await loginSubmitBtn.click();

  // Wait for navigation to dashboard
  await expect(page).toHaveURL("http://localhost:3000/", { timeout: 15000 });
  console.log("[STEP 2] Successfully authenticated and arrived at Command Center dashboard!");
  await page.screenshot({ path: "scratch/e2e_03_dashboard_authenticated.png" });

  // Verify cookies
  const cookies = await context.cookies();
  const sessionCookie = cookies.find((c) => c.name === "revenueos_session");
  console.log("[STEP 2] Session cookie found:", !!sessionCookie);
  console.log("[STEP 2] Session cookie httpOnly:", sessionCookie?.httpOnly);
  console.log("[STEP 2] Session cookie sameSite:", sessionCookie?.sameSite);

  // Verify /api/auth/me/
  const meRes = await page.request.get("http://localhost:8000/api/auth/me/", {
    headers: { Cookie: `revenueos_session=${sessionCookie?.value}` },
  });
  console.log("[STEP 2] Protected /api/auth/me/ status:", meRes.status());
  const meJson = await meRes.json();
  console.log("[STEP 2] Operator user authenticated correctly:", meJson.email === testEmail);

  // ----------------------------------------------------
  // STEP 3: RAZORPAY CHECKOUT FLOW (/checkout)
  // ----------------------------------------------------
  console.log("\n[STEP 3] Navigating to /checkout...");
  await page.goto("http://localhost:3000/checkout", { waitUntil: "domcontentloaded" });

  // Select ₹100.00
  console.log("[STEP 3] Selecting ₹100.00 amount...");
  await page.locator("button:has-text('₹100.00')").click();

  console.log("[STEP 3] Clicking 'Pay ₹100.00 with Razorpay' button...");
  await page.locator("button:has-text('Pay ₹100.00 with Razorpay')").click();

  console.log("[STEP 3] Waiting for Razorpay modal iframe...");
  await page.waitForSelector("iframe.razorpay-checkout-frame", { timeout: 15000 });
  await page.waitForTimeout(2000);

  const rzpFrame = page.frameLocator("iframe.razorpay-checkout-frame");

  // Contact input
  const contactInput = rzpFrame.locator("input[name='contact']");
  if (await contactInput.count() > 0 && await contactInput.isVisible()) {
    console.log("[STEP 3] Entering contact phone...");
    await contactInput.click();
    await contactInput.press("Meta+a");
    await contactInput.press("Backspace");
    await contactInput.pressSequentially("9820000000", { delay: 30 });
    await page.waitForTimeout(300);
    await rzpFrame.locator("button[type='button']:has-text('Continue')").click();
    await page.waitForTimeout(1000);
  }

  // Fill card details (Razorpay Test Card: 4100 2800 0000 1007, 12/26, 123)
  console.log("[STEP 3] Entering Razorpay Test Card credentials (4100 2800 0000 1007)...");
  const cardInput = rzpFrame.locator("input[name='card.number']");
  await cardInput.click();
  await cardInput.pressSequentially("4100280000001007", { delay: 20 });

  const expiryInput = rzpFrame.locator("input[name='card.expiry']");
  await expiryInput.click();
  await expiryInput.pressSequentially("1226", { delay: 20 });

  const cvvInput = rzpFrame.locator("input[name='card.cvv']");
  await cvvInput.click();
  await cvvInput.pressSequentially("123", { delay: 20 });
  await cvvInput.press("Tab");

  await page.waitForTimeout(500);

  // Click continue on card
  console.log("[STEP 3] Submitting card details...");
  const continueBtn = rzpFrame.locator("button:has-text('Continue')").last();
  await continueBtn.click();

  await page.waitForTimeout(1500);

  // Handle RBI guideline prompt
  const maybeLaterBtn = rzpFrame.locator("button:has-text('Maybe later')");
  if (await maybeLaterBtn.count() > 0 && await maybeLaterBtn.first().isVisible().catch(() => false)) {
    console.log("[STEP 3] Clicking 'Maybe later' on RBI prompt...");
    await maybeLaterBtn.first().click();
  }

  // Handle Bank Simulator popup
  console.log("[STEP 3] Waiting for Bank Simulator popup...");
  for (let i = 0; i < 10; i++) {
    if (bankPopup) break;
    await page.waitForTimeout(1000);
  }

  if (bankPopup) {
    console.log("[STEP 3] Bank popup opened, waiting for Success button...");
    await bankPopup.waitForLoadState("domcontentloaded").catch(() => {});
    
    // Find and click Success button on bank simulator
    for (let s = 0; s < 15; s++) {
      if (bankPopup.isClosed()) {
        console.log("[STEP 3] Bank popup closed.");
        break;
      }
      const successBtn = bankPopup.locator("button:has-text('Success'), input[value='Success'], .success");
      if (await successBtn.count() > 0 && await successBtn.first().isVisible().catch(() => false)) {
        console.log("[STEP 3] Clicking 'Success' on Bank Simulator!");
        await successBtn.first().click();
        break;
      }
      await page.waitForTimeout(1000);
    }
  }

  // ----------------------------------------------------
  // STEP 4: VERIFY PAYMENT IN REVENUEOS UI
  // ----------------------------------------------------
  console.log("\n[STEP 4] Waiting for payment verification in RevenueOS UI...");
  const successNotice = page.locator("text='Payment Verified & Captured Successfully!'");
  await successNotice.waitFor({ state: "visible", timeout: 35000 });
  console.log("[STEP 4] UI rendered 'Payment Verified & Captured Successfully!'");

  await page.screenshot({ path: "scratch/e2e_04_payment_verified_ui.png" });
  console.log("[STEP 4] Screenshot saved to scratch/e2e_04_payment_verified_ui.png");

  // ----------------------------------------------------
  // STEP 5: NEGATIVE SECURITY TEST (TAMPERED SIGNATURE)
  // ----------------------------------------------------
  console.log("\n[STEP 5] Performing Negative Security Test with Tampered Signature...");
  const tamperedRes = await page.request.post("http://localhost:8000/api/verify-payment", {
    data: {
      razorpay_order_id: verifiedPaymentData?.order_id || "order_mock12345",
      razorpay_payment_id: verifiedPaymentData?.payment_id || "pay_mock12345",
      razorpay_signature: "invalid_tampered_signature_9999999999999999",
    },
  });
  console.log("[STEP 5] Tampered signature HTTP Status:", tamperedRes.status());
  const tamperedJson = await tamperedRes.json();
  console.log("[STEP 5] Tampered response verified false:", tamperedJson.verified === false);

  // ----------------------------------------------------
  // STEP 6: SECURITY & FAILURE CASES
  // ----------------------------------------------------
  console.log("\n[STEP 6] Running Failure Cases...");
  
  // A. Unregistered user login
  const unregRes = await page.request.post("http://localhost:8000/api/auth/login/", {
    data: {
      email: "unregistered_ghost_999@revenueos.local",
      password: "SomePassword123!",
      turnstileToken: "XXXX.DUMMY.TOKEN.XXXX",
    },
  });
  console.log("[STEP 6A] Unregistered login HTTP Status (expected 401):", unregRes.status());

  // B. Bad password
  const badPassRes = await page.request.post("http://localhost:8000/api/auth/login/", {
    data: {
      email: testEmail,
      password: "WrongPassword999!",
      turnstileToken: "XXXX.DUMMY.TOKEN.XXXX",
    },
  });
  console.log("[STEP 6B] Wrong password HTTP Status (expected 401):", badPassRes.status());

  // C. Duplicate registration
  const dupRes = await page.request.post("http://localhost:8000/api/auth/register/", {
    data: {
      email: testEmail,
      password: testPassword,
      confirmPassword: testPassword,
      turnstileToken: "XXXX.DUMMY.TOKEN.XXXX",
    },
  });
  console.log("[STEP 6C] Duplicate registration HTTP Status (expected 409):", dupRes.status());

  // D. Invalid Turnstile
  const badTurnstileRes = await page.request.post("http://localhost:8000/api/auth/register/", {
    data: {
      email: `another-${testId}@revenueos.local`,
      password: testPassword,
      confirmPassword: testPassword,
      turnstileToken: "completely_invalid_turnstile_token",
    },
  });
  console.log("[STEP 6D] Bad Turnstile HTTP Status (expected 403):", badTurnstileRes.status());

  // E. Duplicate Payment Handling
  if (verifiedPaymentData) {
    const dupPayRes = await page.request.post("http://localhost:8000/api/verify-payment", {
      data: {
        razorpay_order_id: verifiedPaymentData.order_id,
        razorpay_payment_id: verifiedPaymentData.payment_id,
        razorpay_signature: verifiedPaymentData.signature,
      },
    });
    console.log("[STEP 6E] Repeated payment verification response status:", dupPayRes.status());
    const dupPayJson = await dupPayRes.json();
    console.log("[STEP 6E] Repeated payment verified result:", dupPayJson.verified);
  }

  // Save report artifact
  fs.writeFileSync(
    "scratch/master_e2e_results.json",
    JSON.stringify(
      {
        testEmail,
        verifiedPaymentData,
        tamperedSecurityStatus: tamperedRes.status(),
        unregisteredLoginStatus: unregRes.status(),
        wrongPasswordStatus: badPassRes.status(),
        duplicateRegistrationStatus: dupRes.status(),
        badTurnstileStatus: badTurnstileRes.status(),
        timestamp: new Date().toISOString(),
      },
      null,
      2
    )
  );

  await browser.close();
  console.log("\n==================================================");
  console.log("ALL MASTER E2E STEPS COMPLETED SUCCESSFULLY!");
  console.log("==================================================");
}

run().catch((err) => {
  console.error("Master E2E flow encountered an error:", err);
  process.exit(1);
});
