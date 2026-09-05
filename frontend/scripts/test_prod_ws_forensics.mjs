import { chromium } from "@playwright/test";

async function runForensics() {
  console.log("==================================================");
  console.log("PHASE 4A/4B/4C — REAL BROWSER WSS & COOKIE FORENSICS");
  console.log("==================================================");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on("response", async (res) => {
    if (res.url().includes("/api/auth/")) {
      console.log(`[HTTP Response] ${res.status()} ${res.url()}`);
      const setCookie = res.headers()["set-cookie"];
      if (setCookie) {
        console.log(`[Set-Cookie Header]:`, setCookie.replace(/revenueos_session=[^;]+/, "revenueos_session=[REDACTED]"));
      }
    }
  });

  page.on("websocket", (ws) => {
    console.log(`[WebSocket Created]: ${ws.url()}`);
    ws.on("framesent", (event) => console.log(`  -> Frame Sent: ${event.payload}`));
    ws.on("framereceived", (event) => console.log(`  <- Frame Received: ${event.payload}`));
    ws.on("close", () => console.log(`  [WebSocket Closed]`));
    ws.on("socketerror", (err) => console.log(`  [WebSocket Error]:`, err));
  });

  page.on("console", (msg) => {
    console.log(`[Browser Console ${msg.type()}]: ${msg.text()}`);
  });

  // Step 1: Register a test account on live production
  const testEmail = `operator_forensics_${Date.now()}@revenueos.live`;
  const testPassword = "Password123!";
  console.log(`Registering production user: ${testEmail}...`);

  const regRes = await fetch("https://revenueos-backend-f81a.onrender.com/api/auth/register/", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Origin": "https://revenueos.vercel.app" },
    body: JSON.stringify({
      email: testEmail,
      password: testPassword,
      confirmPassword: testPassword,
      name: "Forensic Operator",
      company: "RevenueOS Live",
    }),
  });
  console.log(`Registration status: ${regRes.status}`);
  const regJson = await regRes.json();
  console.log(`Registration response:`, regJson);

  // Step 2: Navigate to Vercel production login page
  console.log("\nNavigating to https://revenueos.vercel.app/login...");
  await page.goto("https://revenueos.vercel.app/login", { waitUntil: "networkidle" });

  // Fill credentials and click Sign In
  console.log("Filling login credentials on production Vercel...");
  await page.fill("#email", testEmail);
  await page.fill("#password", testPassword);
  await page.click("button[type='submit']");

  // Wait for navigation or response
  await page.waitForTimeout(5000);
  console.log(`Current page URL after login: ${page.url()}`);

  // Inspect cookies stored in the browser context
  const cookies = await context.cookies();
  console.log("\n[Browser Stored Cookies]:");
  for (const c of cookies) {
    console.log(`  Cookie: ${c.name}, Domain: ${c.domain}, Path: ${c.path}, HttpOnly: ${c.httpOnly}, Secure: ${c.secure}, SameSite: ${c.sameSite}`);
  }

  // Check if session cookie exists for onrender.com
  const renderCookies = await context.cookies("https://revenueos-backend-f81a.onrender.com");
  console.log(`\nCookies accessible to https://revenueos-backend-f81a.onrender.com:`, renderCookies.map(c => ({ name: c.name, domain: c.domain, sameSite: c.sameSite })));

  // Test fetch /api/auth/me/ from the page context
  console.log("\nExecuting fetch /api/auth/me/ from browser page context...");
  const meResult = await page.evaluate(async () => {
    try {
      const res = await fetch("https://revenueos-backend-f81a.onrender.com/api/auth/me/", {
        credentials: "include",
      });
      const data = await res.json();
      return { status: res.status, data };
    } catch (e) {
      return { error: e.message };
    }
  });
  console.log(`Browser fetch /api/auth/me/ result:`, meResult);

  // Test WebSocket connection from page context
  console.log("\nTesting WebSocket connection directly from browser page context...");
  const wsResult = await page.evaluate(async () => {
    return new Promise((resolve) => {
      const socket = new WebSocket("wss://revenueos-backend-f81a.onrender.com/ws/v1/app/");
      let opened = false;
      socket.onopen = () => {
        opened = true;
        socket.close();
        resolve({ success: true, opened: true });
      };
      socket.onerror = () => {
        // error event
      };
      socket.onclose = (e) => {
        if (!opened) {
          resolve({ success: false, code: e.code, reason: e.reason });
        }
      };
      setTimeout(() => {
        if (!opened) {
          socket.close();
          resolve({ success: false, timeout: true });
        }
      }, 8000);
    });
  });
  console.log(`Browser WebSocket result:`, wsResult);

  await browser.close();
}

runForensics().catch(console.error);
