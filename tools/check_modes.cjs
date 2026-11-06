// User / developer mode: the default menu, the prompt on a developer page, the switch and its persistence.
const { chromium } = require("playwright");
const assert = require("assert/strict");
const fs = require("fs"), os = require("os"), path = require("path");
const { prepare, start, stop } = require("./lib/fixture.cjs");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-modes-"));
prepare(tmp);
const PORT = 8821;
(async () => {
  let browser;
  try {
    start(tmp, "E52", "RM-469", PORT);
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}),
      args: ["--no-sandbox"],
    });
    const open = async (lang, width, hash = "#phone/overview", mode) => {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      await context.addInitScript(([l, m]) => {
        localStorage.setItem("symport-language", l);
        if (m) localStorage.setItem("symport-mode", m); // no saved choice = the real first start
      }, [lang, mode]);
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      page.errors = [];
      page.on("pageerror", (e) => page.errors.push(e.message));
      for (let i = 0; i < 60; i++) { try { await page.goto(`http://127.0.0.1:${PORT}/next/${hash}`); break; } catch { await new Promise((r) => setTimeout(r, 250)); } }
      await page.locator("main").waitFor();
      return page;
    };
    const menuLinks = (page) => page.locator(".sidebar-menu a.nav-link");

    // 1. First start: user mode.
    let page = await open("en", 1366);
    await page.getByRole("button", { name: "User", exact: true }).waitFor();
    assert.equal(await page.locator('.mode-switch button[data-mode="user"]').getAttribute("aria-pressed"), "true");
    const names = await menuLinks(page).allTextContents();
    for (const hidden of ["Emulator Lab", "SDK & build", "Firmware & ROM Explorer", "Custom firmware", "Jailbreak Manager", "Certificate Inspector", "Dependencies", "Reborn for N95", "Add-ons & patches"])
      assert(!names.some((n) => n.includes(hidden)), "hidden in user mode: " + hidden);
    for (const shown of ["File manager", "Contacts", "Backups", "App catalog", "Themes", "Ringtone studio", "Network & TLS", "Device diagnostics", "Operations log"])
      assert(names.some((n) => n.includes(shown)), "shown in user mode: " + shown);
    assert.equal(await page.getByTestId("mode-badge").count(), 0);

    // 2. A developer page opened by link explains itself.
    await page.evaluate(() => { location.hash = "#dev/lab"; });
    await page.getByText("This section is for developer mode").waitFor();
    await page.getByRole("button", { name: /Turn on developer mode/ }).click();
    await page.getByTestId("mode-badge").waitFor();
    await page.getByRole("heading", { name: "Emulator Lab", level: 1 }).waitFor();
    const devNames = await menuLinks(page).allTextContents();
    for (const shown of ["Emulator Lab", "SDK & build", "Firmware & ROM Explorer", "Custom firmware", "Reborn for N95"])
      assert(devNames.some((n) => n.includes(shown)), "shown in developer mode: " + shown);
    assert.equal(await page.evaluate(() => localStorage.getItem("symport-mode")), "developer");

    // 3. The choice is remembered across a reload and can be switched back from the menu.
    await page.reload();
    await page.getByTestId("mode-badge").waitFor();
    await page.locator('.mode-switch button[data-mode="user"]').click();
    await page.getByText("This section is for developer mode").waitFor();
    assert.equal(await page.getByTestId("mode-badge").count(), 0);
    await page.close();

    // 4. Recovery centre: experimental wizards only in developer mode.
    page = await open("en", 1366, "#revive/home");
    await page.locator('[data-wizard="network"]').waitFor();
    assert.equal(await page.locator('[data-wizard="reborn"]').count(), 0);
    assert.equal(await page.locator('[data-wizard="addons"]').count(), 0);
    await page.locator('.mode-switch button[data-mode="developer"]').click();
    await page.locator('[data-wizard="reborn"]').waitFor();
    await page.locator('[data-wizard="addons"]').waitFor();
    await page.close();

    // 5. Russian wording and the phone layout (the switch lives in the drawer).
    page = await open("ru", 390, "#phone/overview", "user");
    await page.getByRole("button", { name: "Открыть меню" }).click();
    await page.getByRole("button", { name: "Разработчик", exact: true }).click();
    await page.getByRole("button", { name: /Разработка и эмуляция/ }).click(); // the group appears collapsed
    await page.getByRole("link", { name: "Emulator Lab" }).waitFor();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "no horizontal overflow");
    assert.deepEqual(page.errors, []);
    await page.close();
    console.log("PASS modes: user mode by default, developer pages behind a prompt, switch persisted, recovery wizards gated, RU/mobile");
  } finally {
    if (browser) await browser.close();
    stop();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => { console.error(e); process.exit(1); });
