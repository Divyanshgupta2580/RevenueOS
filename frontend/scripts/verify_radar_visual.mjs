/**
 * Visual verification and responsive viewport validation for Revenue Radar.
 * Validates viewports: 1440x900, 1280x800, 1024x768, 768x1024, 390x844.
 * Asserts zero horizontal overflow and captures screenshots for artifact documentation.
 */

import { chromium } from "playwright";
import path from "path";

const ARTIFACTS_DIR = "/Users/apple/.gemini/antigravity-ide/brain/65a0b058-4b04-4a9e-8f6b-28bb66fd45cc";

const VIEWPORTS = [
  { name: "desktop_1440x900", width: 1440, height: 900 },
  { name: "laptop_1280x800", width: 1280, height: 800 },
  { name: "tablet_landscape_1024x768", width: 1024, height: 768 },
  { name: "tablet_portrait_768x1024", width: 768, height: 1024 },
  { name: "mobile_390x844", width: 390, height: 844 },
];

async function runVisualValidation() {
  console.log("Launching browser for Revenue Radar visual verification...");
  const browser = await chromium.launch({ headless: true });

  const results = [];

  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    // Mock operator session
    await page.route("**/api/auth/me/", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authenticated: true,
          user: { username: "operator", role: "operator" },
        }),
      });
    });

    await page.goto("http://localhost:3000/", { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);

    // Verify horizontal overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const innerWidth = await page.evaluate(() => window.innerWidth);

    const screenshotPath = path.join(ARTIFACTS_DIR, `radar_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: false });

    console.log(`Viewport ${vp.name} (${vp.width}x${vp.height}):`);
    console.log(`  ScrollWidth: ${scrollWidth}px, InnerWidth: ${innerWidth}px`);
    console.log(`  Horizontal overflow: ${hasHorizontalOverflow ? "FAILED" : "PASSED (0px overflow)"}`);
    console.log(`  Screenshot saved: ${screenshotPath}`);

    results.push({
      viewport: vp.name,
      width: vp.width,
      height: vp.height,
      hasOverflow: hasHorizontalOverflow,
      screenshot: screenshotPath,
    });

    // On 1440x900, if an opportunity exists or can be inspected, test the drawer
    if (vp.name === "desktop_1440x900") {
      const inspectBtn = page.locator("button:has-text('Inspect')").first();
      const hasInspectBtn = await inspectBtn.isVisible().catch(() => false);
      if (hasInspectBtn) {
        await inspectBtn.click();
        await page.waitForTimeout(600);
        const drawerScreenshot = path.join(ARTIFACTS_DIR, "radar_opportunity_drawer.png");
        await page.screenshot({ path: drawerScreenshot });
        console.log(`  Opportunity drawer screenshot saved: ${drawerScreenshot}`);
      }
    }

    await context.close();
  }

  await browser.close();

  const allPassed = results.every((r) => !r.hasOverflow);
  console.log("\n==========================================");
  console.log(`Responsive Viewport Validation: ${allPassed ? "ALL PASSED" : "SOME FAILED"}`);
  console.log("==========================================");

  if (!allPassed) {
    process.exit(1);
  }
}

runVisualValidation().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
