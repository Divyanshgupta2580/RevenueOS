import { chromium } from "playwright";

async function diagnoseProdAuth() {
  console.log("==================================================");
  console.log("DIAGNOSING PRODUCTION AUTH FLOW: https://revenueos.vercel.app");
  console.log("==================================================");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Monitor network
  page.on("request", (req) => {
    console.log(`[REQ] ${req.method()} ${req.url()}`);
    if (req.url().includes("/api/auth/") || req.url().includes("supabase") || req.url().includes("onrender.com")) {
      console.log(`      Headers:`, JSON.stringify(req.headers()));
      console.log(`      PostData:`, req.postData());
    }
  });

  page.on("response", async (res) => {
    if (res.url().includes("/api/auth/") || res.url().includes("supabase") || res.url().includes("onrender.com") || res.status() >= 400) {
      console.log(`[RES] ${res.status()} ${res.url()}`);
      console.log(`      Headers:`, JSON.stringify(res.headers()));
      try {
        const body = await res.text();
        console.log(`      Body:`, body.slice(0, 300));
      } catch {}
    }
  });

  page.on("console", (msg) => {
    console.log(`[CONSOLE ${msg.type()}]:`, msg.text());
  });

  page.on("pageerror", (err) => {
    console.log(`[PAGE ERROR]:`, err.message);
  });

  console.log("\n1. Navigating to https://revenueos.vercel.app/login...");
  await page.goto("https://revenueos.vercel.app/login");
  await page.waitForLoadState("networkidle");

  console.log("Page title:", await page.title());
  console.log("Current URL:", page.url());

  // Inspect form elements
  const inputs = await page.locator("input").all();
  console.log(`Found ${inputs.length} inputs:`);
  for (const input of inputs) {
    const id = await input.getAttribute("id");
    const type = await input.getAttribute("type");
    const name = await input.getAttribute("name");
    const placeholder = await input.getAttribute("placeholder");
    console.log(`  - id='${id}' type='${type}' name='${name}' placeholder='${placeholder}'`);
  }

  const buttons = await page.locator("button").all();
  console.log(`Found ${buttons.length} buttons:`);
  for (const btn of buttons) {
    const text = await btn.innerText();
    const type = await btn.getAttribute("type");
    console.log(`  - type='${type}' text='${text}'`);
  }

  // Fill credentials
  console.log("\n2. Filling credentials...");
  await page.fill("input[type='email']", "operator@revenueos.local");
  await page.fill("input[type='password']", "Password123!");

  console.log("\n3. Clicking submit button...");
  await Promise.all([
    page.waitForNavigation({ timeout: 10000 }).catch(() => console.log("Navigation timed out or stayed on page")),
    page.click("button[type='submit']"),
  ]);

  await page.waitForTimeout(3000);

  console.log("\n4. State after submit:");
  console.log("Current URL:", page.url());

  const cookies = await context.cookies();
  console.log("Stored cookies:", cookies.map(c => ({
    name: c.name,
    domain: c.domain,
    path: c.path,
    sameSite: c.sameSite,
    secure: c.secure,
    httpOnly: c.httpOnly,
  })));

  await browser.close();
}

diagnoseProdAuth().catch(console.error);
