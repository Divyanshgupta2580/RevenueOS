import { chromium } from "playwright";

async function runTrace() {
  console.log("==================================================");
  console.log("TESTING COMPLETE AUTHENTICATION FLOW (STEPS 1 - 9)");
  console.log("Target Backend: https://revenueos-backend-f81a.onrender.com");
  console.log("Target Frontend: http://localhost:3000 (RevenueOS Repository Code)");
  console.log("==================================================");

  // 1. First test raw HTTP flow with node fetch
  console.log("\n[STEP 1 - 5]: Raw HTTP POST /api/auth/login/ to Render backend...");
  const loginPayload = {
    username: "operator@revenueos.local",
    password: "Password123!"
  };

  const loginRes = await fetch("https://revenueos-backend-f81a.onrender.com/api/auth/login/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Origin": "http://localhost:3000"
    },
    body: JSON.stringify(loginPayload)
  });

  console.log("Step 2 - Status:", loginRes.status, loginRes.statusText);
  const setCookie = loginRes.headers.get("set-cookie");
  console.log("Step 4 - Set-Cookie Header:", setCookie);
  const loginJson = await loginRes.json();
  console.log("Step 3 - Django Response Body:", loginJson);

  if (!setCookie) {
    console.error("FAIL: No Set-Cookie header received!");
    return;
  }

  // Extract cookie
  const cookieMatch = setCookie.match(/revenueos_session=([^;]+)/);
  const sessionToken = cookieMatch ? cookieMatch[1] : null;
  console.log("Extracted session cookie present:", !!sessionToken);

  // Step 6: Test GET /api/auth/me/ with Cookie header
  console.log("\n[STEP 6]: Testing GET /api/auth/me/ with Cookie header...");
  const meRes = await fetch("https://revenueos-backend-f81a.onrender.com/api/auth/me/", {
    headers: {
      "Cookie": `revenueos_session=${sessionToken}`,
      "Origin": "http://localhost:3000"
    }
  });

  console.log("Step 6 - GET /api/auth/me/ Status:", meRes.status);
  const meJson = await meRes.json();
  console.log("Step 6 - GET /api/auth/me/ Body:", meJson);

  // Check CORS headers on meRes
  console.log("CORS Access-Control-Allow-Origin:", meRes.headers.get("access-control-allow-origin"));
  console.log("CORS Access-Control-Allow-Credentials:", meRes.headers.get("access-control-allow-credentials"));

  // 2. Now test REAL browser flow
  console.log("\n[STEP 7 - 9]: Testing in real Chromium browser against Next.js + Render backend...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on("request", (req) => {
    if (req.url().includes("/api/auth/") || req.url().includes("/ws/")) {
      console.log(`[BROWSER REQ] ${req.method()} ${req.url()}`);
      console.log(`              Headers:`, req.headers());
    }
  });

  page.on("response", async (res) => {
    if (res.url().includes("/api/auth/")) {
      console.log(`[BROWSER RES] ${res.status()} ${res.url()}`);
      console.log(`              Headers:`, res.headers());
      try {
        console.log(`              Body:`, (await res.text()).slice(0, 200));
      } catch {}
    }
  });

  page.on("console", (msg) => console.log(`[BROWSER CONSOLE ${msg.type()}]:`, msg.text()));

  console.log("Navigating to http://localhost:3000/login...");
  await page.goto("http://localhost:3000/login");
  await page.waitForLoadState("networkidle");

  console.log("Filling form...");
  await page.fill("#email", "operator@revenueos.local");
  await page.fill("#password", "Password123!");

  console.log("Clicking Sign In button...");
  await page.click("button[type='submit']");

  // Wait for navigation
  await page.waitForTimeout(3000);

  console.log("\nURL after login submit:", page.url());

  const cookies = await context.cookies();
  console.log("Stored cookies after login:", cookies.map(c => ({
    name: c.name,
    domain: c.domain,
    path: c.path,
    sameSite: c.sameSite,
    secure: c.secure,
    httpOnly: c.httpOnly
  })));

  // If redirected to dashboard, check if it stays on dashboard
  if (page.url().includes("/login")) {
    console.error("FAIL: Browser redirected back to /login!");
  } else {
    console.log("SUCCESS: Reached dashboard at", page.url());
    console.log("Testing page reload while authenticated...");
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("URL after reload:", page.url());
  }

  await browser.close();
}

runTrace().catch(console.error);
