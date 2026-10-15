// The console's dakit topbar shell, driven in a real browser.
//
// Run through tests/test_browser.py, which starts tests/browser/server.py and
// passes its address in DQ_BASE. Playwright is resolved from PLAYWRIGHT_MODULE
// or the usual node resolution; the pytest wrapper skips when it is missing.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.env.DQ_BASE;

let browser;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });

async function open(path, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...options });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(BASE + path, { waitUntil: "networkidle" });
  return { page, context, errors };
}

const focusedId = (page) => page.evaluate(() => document.activeElement && (document.activeElement.id || document.activeElement.className));

test("a pointer opens the account menu below the bar, Escape closes it back to the trigger", async () => {
  const { page, context, errors } = await open("/admin");
  const trigger = page.locator(".dk-account-trigger");
  const menu = page.locator("#dk-account-menu");
  await trigger.click();
  assert.equal(await trigger.getAttribute("aria-expanded"), "true");
  assert.ok(await menu.isVisible());
  // Pointer opening focuses the menu itself, so no row shows a ring.
  assert.equal(await page.evaluate(() => document.activeElement.id), "dk-account-menu");
  // It drops below the bar, aligned to the right edge, inside the viewport.
  const box = await menu.boundingBox();
  assert.ok(box.y >= 48, `menu top ${box.y} overlaps the 48px bar`);
  assert.ok(box.x + box.width <= 1440 - 8);
  await page.keyboard.press("Escape");
  assert.ok(await menu.isHidden());
  assert.equal(await trigger.getAttribute("aria-expanded"), "false");
  assert.ok(await page.evaluate(() => document.activeElement.matches(".dk-account-trigger")));
  assert.deepEqual(errors, []);
  await context.close();
});

test("the keyboard opens the menu on its first row and arrows move through the rows", async () => {
  const { page, context } = await open("/admin");
  await page.focus(".dk-account-trigger");
  await page.keyboard.press("Enter");
  assert.ok(await page.evaluate(() => document.activeElement.matches('[role="switch"][data-appearance-toggle]')));
  await page.keyboard.press("ArrowDown");
  assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), "Sign out");
  await page.keyboard.press("ArrowDown");
  assert.ok(await page.evaluate(() => document.activeElement.matches('[role="switch"]')), "ArrowDown wraps to the first row");
  await page.keyboard.press("End");
  assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), "Sign out");
  await page.keyboard.press("Escape");
  assert.ok(await page.evaluate(() => document.activeElement.matches(".dk-account-trigger")));
  await context.close();
});

test("an outside click closes the menu, and a second trigger click closes it too", async () => {
  const { page, context } = await open("/admin");
  const trigger = page.locator(".dk-account-trigger");
  const menu = page.locator("#dk-account-menu");
  await trigger.click();
  await page.mouse.click(700, 600);
  assert.ok(await menu.isHidden());
  await trigger.click();
  assert.ok(await menu.isVisible());
  await trigger.click();
  assert.ok(await menu.isHidden());
  await context.close();
});

test("the Dark mode row is a switch that pins the shared dq_theme key and keeps the menu open", async () => {
  const { page, context } = await open("/admin");
  await page.click(".dk-account-trigger");
  const row = page.locator('#dk-account-menu [role="switch"]');
  assert.equal(await row.getAttribute("aria-checked"), "false");
  await row.click();
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "dark");
  assert.equal(await row.getAttribute("aria-checked"), "true");
  assert.equal(await page.evaluate(() => localStorage.getItem("dq_theme")), "dark");
  assert.equal(await page.evaluate(() => localStorage.getItem("dakit-theme")), null);
  assert.ok(await page.locator("#dk-account-menu").isVisible());
  assert.equal((await row.textContent()).trim(), "Dark mode");
  await page.keyboard.press("Space");
  assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), "light");
  assert.equal(await page.evaluate(() => localStorage.getItem("dq_theme")), null);
  await context.close();
});

test("the menu holds no destinations: Sign out is its only link", async () => {
  const { page, context } = await open("/admin");
  const links = await page.$$eval("#dk-account-menu a", (as) => as.map((a) => a.getAttribute("href")));
  assert.deepEqual(links, ["/auth/logout"]);
  await context.close();
});

test("on a phone the bar stays a bar: both links and a 44px avatar fit with no overflow", async () => {
  const { page, context } = await open("/admin", { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  for (const name of ["Live Q&A", "Sessions"]) {
    const box = await page.locator(".dk-shell__nav .dk-nav-item", { hasText: name }).boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 390, `${name} is cut off`);
    assert.ok(box.height >= 44, `${name} is a ${box.height}px target`);
  }
  const avatar = await page.locator(".dk-account-trigger").boundingBox();
  assert.ok(avatar.width >= 44 && avatar.height >= 44 && avatar.x + avatar.width <= 390);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 390);
  // The menu becomes a sheet under the bar, inset from both edges.
  await page.tap(".dk-account-trigger");
  const sheet = await page.locator("#dk-account-menu").boundingBox();
  assert.ok(sheet.x >= 8 && sheet.x + sheet.width <= 390 - 8 && sheet.y >= 48);
  await context.close();
});

test("the skip link is the first stop and lands in main", async () => {
  const { page, context } = await open("/admin");
  await page.keyboard.press("Tab");
  assert.ok(await page.evaluate(() => document.activeElement.matches(".dk-skip-link")));
  await page.keyboard.press("Enter");
  assert.equal(await page.evaluate(() => document.activeElement.id), "main-content");
  await context.close();
});

test("a focused nav item draws the kit's inset ring, so the scrolling bar never clips it", async () => {
  const { page, context } = await open("/admin");
  await page.focus('.dk-shell__nav .dk-nav-item[href="/live"]');
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  const ring = await page.evaluate(() => {
    const style = getComputedStyle(document.activeElement);
    return { offset: style.outlineOffset, width: style.outlineWidth, label: document.activeElement.textContent.trim() };
  });
  assert.equal(ring.label, "Live Q&A");
  assert.equal(ring.width, "3px");
  assert.equal(ring.offset, "-2px");
  await context.close();
});

test("Tab from Sign out out of the page closes the menu, and Tab back in leaves it closed", async () => {
  const { page, context } = await open("/admin");
  await page.focus(".dk-account-trigger");
  await page.keyboard.press("Enter");
  await page.keyboard.press("End");
  assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), "Sign out");
  await page.keyboard.press("Tab");
  await page.waitForFunction(() => document.getElementById("dk-account-menu").hidden, null, { timeout: 3000 });
  assert.equal(await page.getAttribute(".dk-account-trigger", "aria-expanded"), "false");
  await page.keyboard.press("Tab");
  assert.ok(await page.locator("#dk-account-menu").isHidden());
  await context.close();
});

test("a click on the page background closes the menu and returns focus to the trigger", async () => {
  const { page, context } = await open("/admin");
  await page.click(".dk-account-trigger");
  await page.keyboard.press("ArrowDown");
  await page.mouse.click(1400, 860);
  assert.ok(await page.locator("#dk-account-menu").isHidden());
  await page.waitForFunction(() => document.activeElement.matches(".dk-account-trigger"), null, { timeout: 3000 });
  await context.close();
});

for (const [label, viewport] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  test(`selects keep dakit's chevron and its clearance on the ${label}`, async () => {
    const { page, context } = await open("/admin/rooms/R1", { viewport, hasTouch: label === "phone", isMobile: label === "phone" });
    await page.goto(BASE + "/admin", { waitUntil: "networkidle" });
    await page.click("#new-session");
    for (const id of ["new-state", "new-expiry"]) {
      const style = await page.$eval(`#${id}`, (el) => {
        const s = getComputedStyle(el);
        return { appearance: s.appearance, image: s.backgroundImage, position: s.backgroundPositionX, right: s.paddingRight };
      });
      assert.equal(style.appearance, "none", id);
      assert.match(style.image, /^url\("data:image\/svg\+xml/, `${id} lost its chevron`);
      assert.match(style.position, /100%|right/, `${id} chevron is not at the right edge: ${style.position}`);
      assert.equal(style.right, "34px", `${id} text does not clear the chevron`);
    }
    await context.close();
  });
}
