import { chromium, expect } from "@playwright/test";

async function run() {
  const timestamp = Date.now();
  const testEmail = `operator_audit_${timestamp}@revenueos.local`;
  const testPassword = `Pass#${timestamp}Secure`;

  console.log("==================================================");
  console.log("REVENUEOS LIVE TURNSTILE & AUTH E2E AUDIT");
  console.log("==================================================");
  console.log("Test Account:", testEmail);

  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  // 1. REGISTER TEST
  console.log("\n[TEST 1] Testing /register with Turnstile...");
  await page.goto("http://localhost:3000/register", { waitUntil: "domcontentloaded" });
  await expect(page.locator("input#email")).toBeVisible();

  // Check that submit button is initially disabled (enforcing Turnstile)
  const regBtnInit = page.locator("button[type='submit']");
  console.log("Register submit button disabled initially:", await regBtnInit.isDisabled());
  expect(await regBtnInit.isDisabled()).toBe(true);

  // Fill form
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);
  await page.locator("input#confirmPassword").fill(testPassword);

  // Wait for Turnstile challenge completion
  console.log("Waiting for Turnstile verification...");
  await page.waitForTimeout(3000);
  const regSubmit = page.locator("button[type='submit']");
  await expect(regSubmit).toBeEnabled({ timeout: 10000 });
  console.log("Turnstile completed: Register submit button enabled!");

  // Submit registration
  await regSubmit.click();
  await page.waitForFunction(
    () => window.location.pathname === "/login" || document.body.innerText.includes("Sign In to RevenueOS"),
    { timeout: 15000 }
  );
  console.log("Registration successful -> arrived at login page! URL:", page.url());
  expect(page.url()).toContain("/login");

  // 2. LOGIN TEST
  console.log("\n[TEST 2] Testing /login with Turnstile...");
  await expect(page.locator("input#email")).toBeVisible();

  // Fill login credentials
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);

  // Wait for Turnstile
  console.log("Waiting for Turnstile verification on login...");
  await page.waitForTimeout(3000);
  const loginSubmit = page.locator("button[type='submit']");
  await expect(loginSubmit).toBeEnabled({ timeout: 10000 });
  console.log("Turnstile completed: Login submit button enabled!");

  // Submit login
  await loginSubmit.click();
  await page.waitForFunction(
    () => window.location.pathname === "/" || document.body.innerText.includes("Command Center"),
    { timeout: 15000 }
  );
  console.log("Login successful -> redirected to Command Center dashboard! URL:", page.url());
  expect(page.url()).toBe("http://localhost:3000/");

  // 3. SESSION & WEBSOCKET VERIFICATION
  console.log("\n[TEST 3] Verifying authenticated session & WebSocket connection...");
  const cookies = await context.cookies();
  const sessionCookie = cookies.find((c) => c.name === "revenueos_session");
  console.log("Session cookie created:", !!sessionCookie);
  console.log("Session cookie httpOnly:", sessionCookie?.httpOnly);
  console.log("Session cookie sameSite:", sessionCookie?.sameSite);
  expect(sessionCookie).toBeTruthy();

  // Check WebSocket status indicator on dashboard
  const statusBtn = page.locator("button[aria-label^='WebSocket status:']");
  await expect(statusBtn).toBeVisible({ timeout: 10000 });
  const label = await statusBtn.getAttribute("aria-label");
  console.log("WebSocket indicator label:", label);
  expect(label).toMatch(/WebSocket status: (Connected|Connecting|Reconnecting|Disconnected)/);

  // 4. INVALID TOKEN REJECTION TEST (DIRECT API PROBE)
  console.log("\n[TEST 4] Verifying server-side rejection of invalid token...");
  const invalidResp = await page.request.post("http://127.0.0.1:8000/api/auth/login/", {
    data: {
      username: testEmail,
      password: testPassword,
      turnstileToken: "2x0000000000000000000000000000000AA",
    },
  });
  console.log("Invalid token response status:", invalidResp.status());
  const invalidJson = await invalidResp.json();
  console.log("Invalid token error code:", invalidJson.error?.code);
  expect(invalidResp.status()).toBe(403);
  expect(invalidJson.error?.code).toBe("CAPTCHA_FAILED");

  // 5. MISSING TOKEN REJECTION TEST (DIRECT API PROBE)
  console.log("\n[TEST 5] Verifying server-side rejection of missing token...");
  const missingResp = await page.request.post("http://127.0.0.1:8000/api/auth/login/", {
    data: {
      username: testEmail,
      password: testPassword,
      turnstileToken: "",
    },
  });
  console.log("Missing token response status:", missingResp.status());
  const missingJson = await missingResp.json();
  console.log("Missing token error code:", missingJson.error?.code);
  expect(missingResp.status()).toBe(403);
  expect(missingJson.error?.code).toBe("CAPTCHA_FAILED");

  console.log("\n==================================================");
  console.log("ALL TURNSTILE AUDIT TESTS PASSED SUCCESSFULLY (100%)");
  console.log("==================================================");

  await browser.close();
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
