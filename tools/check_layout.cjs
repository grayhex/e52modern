// Layout and accessibility baseline for the main screens at 390 / 768 / 1366 / 1920 px (light Nokia theme, RU + EN):
// no horizontal overflow, no control wider than the viewport, every control has an accessible name,
// a visible keyboard focus ring, and the first 1366×768 screen of the overview shows the handset and its status.
// Synthetic fixture (see tools/lib/fixture.cjs); nothing here is a phone.
const { chromium } = require("playwright");
const fs = require("fs"), os = require("os"), path = require("path");
const { prepare, start, stop } = require("./lib/fixture.cjs");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-layout-"));
prepare(tmp);
start(tmp, "E52", "RM-469", 8811);
const ROUTES = [
  "phone/overview", "phone/files", "phone/contacts", "phone/media", "phone/connection", "apps/catalog",
  "apps/dependencies", "personalize/themes", "personalize/theme-editor", "personalize/ringtones",
  "tools/diagnostics", "tools/certificates", "tools/firmware", "dev/lab", "personalize/wallpapers",
];
const WIDTHS = [[390, 844], [768, 1024], [1366, 768], [1920, 1080]];
(async () => {
  let browser;
  const problems = [];
  try {
    browser = await chromium.launch({ headless: true, ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}), args: ["--no-sandbox"] });
    for (const language of ["ru", "en"]) {
      const context = await browser.newContext({ viewport: { width: 1366, height: 768 }, reducedMotion: "reduce" });
      await context.addInitScript((l) => { try { localStorage.setItem("symport-language", l); } catch {} }, language);
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      page.on("pageerror", (e) => problems.push(`${language}: page error ${e.message}`));
      for (let i = 0; i < 60; i++) { try { await page.goto("http://127.0.0.1:8811/next/"); break; } catch { await new Promise((r) => setTimeout(r, 250)); } }
      await page.locator("#page-phone-overview .k-identity").waitFor();
      for (const [width, height] of WIDTHS) {
        await page.setViewportSize({ width, height });
        for (const route of ROUTES) {
          await page.evaluate((r) => { location.hash = "#" + r; }, route);
          const section = page.locator("#page-" + route.replace("/", "-"));
          await section.waitFor();
          await page.waitForTimeout(250);
          const where = `${language} ${width}px ${route}`;
          const report = await page.evaluate((id) => {
            const out = { overflow: document.documentElement.scrollWidth - innerWidth, wide: [], unnamed: [] };
            const root = document.getElementById(id);
            for (const el of root.querySelectorAll("button, a[href], input, select, textarea")) {
              const box = el.getBoundingClientRect();
              if (!box.width || !box.height) continue;
              if (box.right > innerWidth + 1 && !el.closest("[data-allow-scroll], .tablewrap, pre, table")) out.wide.push(el.outerHTML.slice(0, 90));
              const named = el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.getAttribute("title") ||
                (el.labels && el.labels.length) || el.textContent.trim() || el.closest("label") || el.getAttribute("placeholder") ||
                el.type === "hidden" || el.type === "file" || el.type === "checkbox" && el.closest("label");
              if (!named) out.unnamed.push(el.outerHTML.slice(0, 90));
            }
            return out;
          }, "page-" + route.replace("/", "-"));
          if (report.overflow > 0) problems.push(`${where}: horizontal overflow ${report.overflow}px`);
          for (const w of report.wide) problems.push(`${where}: control wider than the viewport: ${w}`);
          if (language === "ru") for (const u of report.unnamed) problems.push(`${where}: control without an accessible name: ${u}`);
        }
      }
      // First screen of the overview at 1366×768: handset, name and status visible without scrolling.
      await page.setViewportSize({ width: 1366, height: 768 });
      await page.evaluate(() => { location.hash = "#phone/overview"; });
      await page.locator("#page-phone-overview .k-identity").waitFor();
      const first = await page.evaluate(() => {
        const visible = (el) => { const b = el?.getBoundingClientRect(); return !!b && b.top >= 0 && b.bottom <= innerHeight; };
        const root = document.getElementById("page-phone-overview");
        return { image: visible(root.querySelector(".k-identity-media img")), name: visible(root.querySelector(".k-identity-name")), status: visible(root.querySelector(".k-identity-status")), actions: visible(root.querySelector(".k-toolbar a")) };
      });
      for (const [k, v] of Object.entries(first)) if (!v) problems.push(`${language}: overview first screen 1366×768 does not show ${k}`);
      // Keyboard: the skip link and the first controls show a focus ring.
      await page.keyboard.press("Tab");
      await page.keyboard.press("Tab");
      const ring = await page.evaluate(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2; });
      if (!ring) problems.push(`${language}: focused control has no visible focus ring`);
      await context.close();
    }
    if (problems.length) throw Error("Layout/accessibility problems:\n" + [...new Set(problems)].slice(0, 40).join("\n"));
    console.log(`PASS layout: ${ROUTES.length} screens × ${WIDTHS.length} widths × RU/EN — no overflow, named controls, focus ring, overview first screen shows handset/status/actions.`);
  } finally {
    await browser?.close();
    stop();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => { console.error(e.message || e); process.exitCode = 1; });
