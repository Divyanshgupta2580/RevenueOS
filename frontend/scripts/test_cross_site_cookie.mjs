import { chromium } from "@playwright/test";

async function testCrossSiteCookie() {
  console.log("==================================================");
  console.log("TESTING CROSS-SITE COOKIE & WSS AUTHENTICATION");
  console.log("==================================================");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 1. Authenticate directly against Render backend from browser context
  const testEmail = "operator@revenueos.local";
  const testPassword = "Password123!";

  console.log(`Logging in directly via fetch from https://revenueos-backend-f81a.onrender.com...`);
  await page.goto("https://revenueos-backend-f81a.onrender.com/api/health/");

  const loginRes = await page.evaluate(async ({ email, password }) => {
    const res = await fetch("https://revenueos-backend-f81a.onrender.com/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });
    const json = await res.json();
    return { status: res.status, json };
  }, { email: testEmail, password: testPassword });

  console.log("Direct login result on Render:", loginRes);

  const cookiesAfterLogin = await context.cookies("https://revenueos-backend-f81a.onrender.com");
  console.log("Cookies stored for onrender.com:", cookiesAfterLogin.map(c => ({ name: c.name, sameSite: c.sameSite, secure: c.secure, httpOnly: c.httpOnly })));

  // 2. Now navigate to a cross-site origin (e.g. https://revenueos.vercel.app or http://localhost:3000)
  console.log("\nNavigating to cross-site frontend: http://localhost:3000...");
  await page.goto("http://localhost:3000");

  // Check if page can connect to Render WSS with the cookie
  console.log("Attempting WebSocket connection from cross-site page to Render WSS...");
  const wsResult = await page.evaluate(async () => {
    return new Promise((resolve) => {
      const socket = new WebSocket("wss://revenueos-backend-f81a.onrender.com/ws/v1/app/");
      let opened = false;
      socket.onopen = () => {
        opened = true;
        socket.send(JSON.stringify({
          protocolVersion: "v1",
          type: "ping",
          requestId: "test-cross-site",
          timestamp: new Date().toISOString(),
          payload: {}
        }));
      };
      socket.onmessage = (e) => {
        resolve({ success: true, opened: true, data: e.data });
        socket.close();
      };
      socket.onerror = () => {};
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
      }, 10000);
    });
  });

  console.log("Cross-site WebSocket connection result:", wsResult);
  await browser.close();
}

testCrossSiteCookie().catch(console.error);
