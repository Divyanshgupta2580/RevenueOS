import { chromium, expect } from "@playwright/test";

async function run() {
  const timestamp = Date.now();
  const testEmail = `operator_auth_${timestamp}@revenueos.local`;
  const testPassword = `Pass#${timestamp}Secure`;

  console.log("==================================================");
  console.log("REVENUEOS LIVE AUTH & SESSION E2E AUDIT");
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
  console.log("\n[TEST 1] Testing /register direct auth flow...");
  await page.goto("http://localhost:3000/register", { waitUntil: "domcontentloaded" });
  await expect(page.locator("input#email")).toBeVisible();

  // Verify no Turnstile / Cloudflare verification iframe is rendered anywhere
  const challengeIframes = page.locator("iframe[src*='cloudflare'], iframe[src*='turnstile']");
  expect(await challengeIframes.count()).toBe(0);

  // Fill form
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);
  await page.locator("input#confirmPassword").fill(testPassword);

  const regSubmit = page.locator("button[type='submit']");
  await expect(regSubmit).toBeEnabled();
  console.log("Register submit button is immediately enabled for direct submission.");

  // Submit registration
  await regSubmit.click();
  await page.waitForFunction(
    () => window.location.pathname === "/login" || document.body.innerText.includes("Sign In to RevenueOS"),
    { timeout: 15000 }
  );
  console.log("Registration successful -> redirected to login page! URL:", page.url());
  expect(page.url()).toContain("/login");

  // 2. LOGIN TEST
  console.log("\n[TEST 2] Testing /login direct auth flow...");
  await expect(page.locator("input#email")).toBeVisible();

  // Verify no Turnstile / Cloudflare verification iframe is rendered on login
  const loginChallengeIframes = page.locator("iframe[src*='cloudflare'], iframe[src*='turnstile']");
  expect(await loginChallengeIframes.count()).toBe(0);

  // Fill login credentials
  await page.locator("input#email").fill(testEmail);
  await page.locator("input#password").fill(testPassword);

  const loginSubmit = page.locator("button[type='submit']");
  await expect(loginSubmit).toBeEnabled();
  console.log("Login submit button is immediately enabled for direct submission.");

  // Submit login
  await loginSubmit.click();
  await page.waitForFunction(
    () => window.location.pathname === "/" || document.body.innerText.includes("Command Center"),
    { timeout: 15000 }
  );
  console.log("Login successful -> arrived at Command Center dashboard! URL:", page.url());
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

  console.log("\n==================================================");
  console.log("ALL CLEAN AUTH E2E AUDIT TESTS PASSED (100%)");
  console.log("==================================================");

  await browser.close();
}

run().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
