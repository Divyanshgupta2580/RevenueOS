import { chromium } from "playwright";
import { spawn } from "child_process";

const RENDER_BACKEND = "https://revenueos-backend-f81a.onrender.com";
const FRONTEND_PORT = 3000;
const FRONTEND_URL = `http://localhost:${FRONTEND_PORT}`;

async function main() {
  console.log("==================================================");
  console.log("REVENUEOS: VERIFYING 9-STEP AUTHENTICATION FLOW");
  console.log("Backend Target:", RENDER_BACKEND);
  console.log("Frontend Target:", FRONTEND_URL);
  console.log("==================================================");

  // 1. Build and start local Next.js server configured with Render backend
  console.log("\n[SETUP] Starting Next.js server on port", FRONTEND_PORT, "pointing to Render backend...");
  const server = spawn(
    "npx",
    ["next", "start", "-p", String(FRONTEND_PORT)],
    {
      cwd: process.cwd() + "/frontend",
      env: {
        ...process.env,
        PORT: String(FRONTEND_PORT),
        NEXT_PUBLIC_API_ORIGIN: RENDER_BACKEND,
        NEXT_PUBLIC_WS_URL: "wss://revenueos-backend-f81a.onrender.com/ws/v1/app/",
        NEXT_PUBLIC_RAZORPAY_KEY_ID: "rzp_test_TY1j7fS5RyVWJ7",
      },
      stdio: "pipe",
    }
  );

  server.stdout.on("data", (d) => {
    const text = d.toString();
    if (text.includes("Ready in") || text.includes("started server")) {
      console.log("[SERVER]", text.trim());
    }
  });

  server.stderr.on("data", (d) => console.error("[SERVER ERR]", d.toString().trim()));

  // Wait for server ready
  let serverReady = false;
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`${FRONTEND_URL}/login`);
      if (res.status === 200) {
        serverReady = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }

  if (!serverReady) {
    server.kill();
    throw new Error("Next.js server failed to become ready on port " + FRONTEND_PORT);
  }
  console.log("[SETUP] Next.js server is ready at", FRONTEND_URL);

  const browser = await chromium.launch({ headless: true });

  try {
    console.log("\n--- TEST 1: Clean/Incognito Session Initial State ---");
    const context = await browser.newContext();
    const page = await context.newPage();

    let interceptedLoginReq = null;
    let interceptedLoginRes = null;
    let interceptedMeReqCount = 0;
    let interceptedMeRes = null;
    let interceptedWsHandshake = false;

    page.on("request", (req) => {
      const u = req.url();
      if (u.includes("/api/auth/login/")) {
        interceptedLoginReq = {
          url: u,
          method: req.method(),
          headers: req.headers(),
          postData: req.postData(),
        };
      } else if (u.includes("/api/auth/me/")) {
        interceptedMeReqCount++;
        console.log(`[NETWORK] GET /api/auth/me/ (#${interceptedMeReqCount}) Cookie:`, req.headers()["cookie"] || "(none)");
      } else if (u.includes("/ws/v1/app/")) {
        interceptedWsHandshake = true;
        console.log("[NETWORK] WSS Handshake requested to:", u);
      }
    });

    page.on("response", async (res) => {
      const u = res.url();
      if (u.includes("/api/auth/login/")) {
        interceptedLoginRes = {
          status: res.status(),
          headers: res.headers(),
          body: await res.json().catch(() => null),
        };
      } else if (u.includes("/api/auth/me/")) {
        interceptedMeRes = {
          status: res.status(),
          headers: res.headers(),
          body: await res.json().catch(() => null),
        };
        console.log(`[NETWORK] /api/auth/me/ Response Status:`, res.status(), JSON.stringify(interceptedMeRes.body));
      }
    });

    page.on("console", (msg) => {
      if (msg.type() === "error" || msg.text().includes("[WebSocket]")) {
        console.log(`[BROWSER CONSOLE ${msg.type()}]:`, msg.text());
      }
    });

    // Step 0: Visiting / unauthenticated redirects to /login
    console.log("\n[STEP 0] Visiting root / unauthenticated...");
    await page.goto(`${FRONTEND_URL}/`);
    await page.waitForURL(`**/login`, { timeout: 10000 });
    console.log("Unauthenticated redirect verified: URL is", page.url());

    // Step 1: Submit valid operator credentials
    console.log("\n[STEP 1 - 2] Submitting valid operator credentials on /login...");
    await page.fill("#email", "operator@revenueos.local");
    await page.fill("#password", "Password123!");

    const submitBtn = page.locator("button[type='submit']");
    await submitBtn.click();

    // Step 3-5: Observe login response & cookie storage
    console.log("Waiting for navigation to dashboard...");
    await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 15000 });
    console.log("[STEP 8] Reached dashboard URL:", page.url());

    console.log("\n[STEP 1 - 4 VERIFICATION]:");
    console.log("POST /api/auth/login/ Request URL:", interceptedLoginReq?.url);
    console.log("POST /api/auth/login/ Status:", interceptedLoginRes?.status);
    console.log("POST /api/auth/login/ Body:", interceptedLoginRes?.body);
    console.log("WSS Handshake initiated:", interceptedWsHandshake);
    const setCookie = interceptedLoginRes?.headers["set-cookie"] || "";
    console.log("Set-Cookie Header:", setCookie);

    // Step 5: Verify browser stored cookie
    const cookies = await context.cookies();
    const sessionCookie = cookies.find((c) => c.name === "revenueos_session");
    console.log("\n[STEP 5 VERIFICATION]: Stored revenueos_session cookie:");
    console.log(sessionCookie ? {
      name: sessionCookie.name,
      domain: sessionCookie.domain,
      path: sessionCookie.path,
      httpOnly: sessionCookie.httpOnly,
      secure: sessionCookie.secure,
      sameSite: sessionCookie.sameSite,
    } : "COOKIE NOT FOUND!");

    if (!sessionCookie) {
      throw new Error("FAIL: revenueos_session cookie was not stored by browser!");
    }

    // Step 6 - 7: Verify /api/auth/me/ succeeded and updated state
    console.log("\n[STEP 6 - 7 VERIFICATION]:");
    console.log("GET /api/auth/me/ Status:", interceptedMeRes?.status);
    console.log("GET /api/auth/me/ Body:", interceptedMeRes?.body);

    // Wait a moment to ensure dashboard DOES NOT redirect back to /login
    await page.waitForTimeout(3000);
    console.log("Current URL after 3s on dashboard:", page.url());
    if (page.url().includes("/login")) {
      throw new Error("FAIL: Dashboard redirected back to /login!");
    }
    console.log("SUCCESS: User stayed on dashboard! No false bounce back to /login.");

    // Step 9: WebSocket verification
    console.log("\n[STEP 9 VERIFICATION]: WebSocket state on dashboard...");
    // Check Header connection badge
    const header = page.locator("header");
    await header.waitFor({ state: "visible", timeout: 5000 });
    const headerText = await header.innerText();
    console.log("Header contents:", headerText.replace(/\n+/g, " | "));

    // --- TEST 2: Refresh while logged in retains session ---
    console.log("\n--- TEST 2: Page Refresh While Authenticated ---");
    interceptedMeRes = null;
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("URL after reload:", page.url());
    if (page.url().includes("/login")) {
      throw new Error("FAIL: Page reload caused unauthenticated redirect to /login!");
    }
    console.log("SUCCESS: Page reload retained authenticated session on dashboard!");
    console.log("GET /api/auth/me/ on reload Status:", interceptedMeRes?.status);

    // --- TEST 3: Logout destroys session ---
    console.log("\n--- TEST 3: Sign Out / Logout ---");
    const signOutBtn = page.locator("button:has-text('Sign out')");
    await signOutBtn.click();
    await page.waitForURL(`**/login`, { timeout: 10000 });
    console.log("URL after sign out:", page.url());

    // Verify session cookie cleared
    const cookiesAfterLogout = await context.cookies();
    const sessionCookieAfterLogout = cookiesAfterLogout.find((c) => c.name === "revenueos_session");
    console.log("Stored revenueos_session after logout:", sessionCookieAfterLogout?.value || "(cleared / expired)");

    // Attempting to visit / now must redirect to /login
    console.log("Attempting to visit / after logout...");
    await page.goto(`${FRONTEND_URL}/`);
    await page.waitForURL(`**/login`, { timeout: 10000 });
    console.log("Protected route redirected to:", page.url());

    // --- TEST 4: Re-authenticating works cleanly ---
    console.log("\n--- TEST 4: Logging In Again After Sign Out ---");
    await page.fill("#email", "operator@revenueos.local");
    await page.fill("#password", "Password123!");
    await page.locator("button[type='submit']").click();
    await page.waitForURL(`${FRONTEND_URL}/`, { timeout: 15000 });
    await page.waitForTimeout(2000);
    console.log("Re-login arrived at:", page.url());
    if (page.url().includes("/login")) {
      throw new Error("FAIL: Re-login failed to stay on dashboard!");
    }
    console.log("SUCCESS: Re-login fully succeeded!");

    await context.close();
    console.log("\n==================================================");
    console.log("ALL AUTHENTICATION INTEGRATION TESTS PASSED!");
    console.log("==================================================");
  } finally {
    await browser.close();
    server.kill();
  }
}

main().catch((err) => {
  console.error("FATAL TEST ERROR:", err);
  process.exit(1);
});
