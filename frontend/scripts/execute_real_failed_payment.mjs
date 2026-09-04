import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = '/Users/apple/.gemini/antigravity-ide/brain/65a0b058-4b04-4a9e-8f6b-28bb66fd45cc';

async function run() {
  console.log('--- Launching Browser for Real Razorpay Test Mode Failure Execution ---');
  
  // 1. Authenticate via backend to obtain a valid session cookie
  const uniqueUser = `op_fail_${Date.now()}@revenueos.local`;
  const password = "StrongPassword2026!";
  const turnstileToken = "1x0000000000000000000000000000000AA";

  console.log(`Registering operator: ${uniqueUser}...`);
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

  console.log(`Session acquired: ${sessionCookieValue ? "YES" : "NO"}`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
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

  page.on('console', msg => {
    if (msg.type() === 'error' || msg.text().includes('Razorpay') || msg.text().includes('failure') || msg.text().includes('record-failure')) {
      console.log(`[Browser Console]: ${msg.text()}`);
    }
  });

  // Track network requests to record-failure
  page.on('request', req => {
    if (req.url().includes('record-failure')) {
      console.log(`[Network Request] ${req.method()} ${req.url()}`, req.postData());
    }
  });
  page.on('response', async res => {
    if (res.url().includes('record-failure')) {
      console.log(`[Network Response] ${res.status()} ${res.url()}`);
      try {
        const body = await res.text();
        console.log(`[Record-Failure Response Body]: ${body}`);
      } catch {}
    }
  });

  console.log('Navigating to http://localhost:3000/...');
  await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);

  // Click Checkout navigation tab
  console.log('Clicking Checkout tab...');
  const checkoutTab = page.locator("button:has-text('Checkout')");
  await checkoutTab.click();
  await page.waitForTimeout(1500);

  // If "Make Another Payment" is visible, click it
  const makeAnother = page.locator("button:has-text('Make Another Payment')");
  if (await makeAnother.isVisible().catch(() => false)) {
    console.log("Clicking 'Make Another Payment'...");
    await makeAnother.click();
    await page.waitForTimeout(1000);
  }

  // Select ₹1,500 preset
  const preset1500 = page.locator('button:has-text("₹1,500.00")');
  if (await preset1500.isVisible().catch(() => false)) {
    console.log('Selecting ₹1,500.00 preset...');
    await preset1500.click();
    await page.waitForTimeout(500);
  }

  // Click Proceed to Secure Payment
  console.log('Clicking "Proceed to Secure Payment with Razorpay"...');
  const payBtn = page.locator('button:has-text("with Razorpay")');
  await payBtn.click();

  // Wait for Razorpay frame
  console.log('Waiting for Razorpay iframe...');
  await page.waitForTimeout(5000);

  const frames = page.frames();
  console.log(`Total frames found: ${frames.length}`);
  let rzpFrame = null;
  for (const f of frames) {
    const url = f.url();
    console.log(`- Frame URL: ${url}`);
    if (url.includes('razorpay.com')) {
      rzpFrame = f;
    }
  }
  if (rzpFrame) {
    console.log('Razorpay iframe found via frames list');
  }

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/razorpay_modal_opened.png') });
  console.log('Screenshot saved to scratch/razorpay_modal_opened.png');

  console.log('Testing page.frameLocator("iframe.razorpay-checkout-frame")...');
  const rzp = page.frameLocator('iframe.razorpay-checkout-frame');

  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/rzp_checkout_view_initial.png') });

  // If contact prompt still appears for any reason, handle it
  const contactInput = rzp.locator('input[name="contact"]');
  if (await contactInput.count() > 0 && await contactInput.first().isVisible().catch(() => false)) {
    console.log('Contact input visible, filling with 9820123456...');
    await contactInput.first().fill('9820123456');
    await page.waitForTimeout(300);
    const contBtn = rzp.locator('button:has-text("Continue")').last();
    if (await contBtn.isVisible().catch(() => false)) {
      console.log('Clicking Continue on contact prompt...');
      await contBtn.click();
      await page.waitForTimeout(2000);
    }
  }

  // Now fill card details
  const cardNum = rzp.locator('input[name="card.number"]');
  const cardExp = rzp.locator('input[name="card.expiry"]');
  const cardCvv = rzp.locator('input[name="card.cvv"]');

  console.log(`Filling card inputs: standard test card 4111 1111 1111 1111...`);
  await cardNum.first().waitFor({ state: 'visible', timeout: 10000 });
  await cardNum.first().click({ force: true });
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await page.keyboard.type('4111111111111111', { delay: 40 });
  await page.waitForTimeout(300);

  await cardExp.first().click({ force: true });
  await page.keyboard.type('1228', { delay: 40 });
  await page.waitForTimeout(300);

  await cardCvv.first().click({ force: true });
  await page.keyboard.type('123', { delay: 40 });
  await page.waitForTimeout(500);

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/rzp_card_all_filled.png') });
  console.log('Saved scratch/rzp_card_all_filled.png');

  // Find and click the Continue / Pay button
  const submitBtn = rzp.locator('button:has-text("Continue"), button:has-text("Pay"), button:has-text("₹")').last();
  console.log('Clicking Continue/Pay button in Razorpay iframe...');
  await submitBtn.click();
  await page.waitForTimeout(4000);

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/rzp_after_pay_click.png') });

  // Handle "Save your card for future payments?" prompt
  const maybeLaterBtn = rzp.locator('button:has-text("Maybe later"), button:has-text("Skip")');
  if (await maybeLaterBtn.count() > 0 && await maybeLaterBtn.first().isVisible().catch(() => false)) {
    console.log('Found "Maybe later" button! Clicking it...');
    await maybeLaterBtn.first().click();
    await page.waitForTimeout(5000);
  }

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/rzp_after_maybe_later.png') });
  console.log('Saved scratch/rzp_after_maybe_later.png');

  // Check all frames for bank simulator Failure button
  console.log('Checking for bank simulator failure button...');
  for (let attempt = 0; attempt < 8; attempt++) {
    const allFrames = page.frames();
    let clickedSimulator = false;
    for (const f of allFrames) {
      try {
        const foundFail = await f.evaluate(() => {
          const els = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], a'));
          const btn = els.find(e => {
            const text = (e.innerText || e.value || '').trim().toLowerCase();
            return text === 'failure' || text === 'fail' || text.includes('fail');
          });
          if (btn && typeof btn.click === 'function') {
            btn.click();
            return (btn.innerText || btn.value || 'Clicked Failure');
          }
          return null;
        });
        if (foundFail) {
          console.log(`Clicked Failure button ("${foundFail}") in frame ${f.url()}!`);
          clickedSimulator = true;
          break;
        }
      } catch {}
    }
    if (clickedSimulator) break;
    await page.waitForTimeout(2000);
  }

  // Wait for failure ingestion to complete
  console.log('Waiting for payment.failed ingestion and /api/record-failure...');
  await page.waitForTimeout(10000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'scratch/rzp_final_result.png') });

  await browser.close();
  console.log('Test run finished.');
}

run().catch(err => {
  console.error('Fatal error in script:', err);
  process.exit(1);
});
