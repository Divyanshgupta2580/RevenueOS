import { chromium } from "@playwright/test";

async function run() {
  console.log("Launching headless Chromium...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  console.log("Navigating to http://localhost:3000/register...");
  await page.goto("http://localhost:3000/register", { waitUntil: "domcontentloaded" });

  const title = await page.title();
  console.log("Page title:", title);

  const buttonDisabled = await page.locator("button[type='submit']").isDisabled();
  console.log("Submit button disabled before turnstile:", buttonDisabled);

  // Wait up to 5 seconds for Turnstile to populate token
  console.log("Waiting for Turnstile widget...");
  try {
    // Check if Turnstile iframe or checkbox exists
    const turnstileIframe = page.frameLocator("iframe[src*='cloudflare']");
    const checkbox = turnstileIframe.locator("input[type='checkbox'], #challenge-stage");
    if (await checkbox.count() > 0) {
      console.log("Turnstile checkbox found, clicking...");
      await checkbox.first().click();
    }
  } catch (e) {
    console.log("Turnstile interaction note:", e.message);
  }

  // Wait a bit to see if token callback fires
  await page.waitForTimeout(3000);

  const buttonDisabledAfter = await page.locator("button[type='submit']").isDisabled();
  console.log("Submit button disabled after wait:", buttonDisabledAfter);

  await browser.close();
}

run().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
