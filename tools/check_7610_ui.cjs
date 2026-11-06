// Nokia 7610 (S60 2nd Edition): its own identity and artwork, and only honest states for what the transport did not prove.
const { chromium } = require("playwright");
const assert = require("assert/strict");
const fs = require("fs"), os = require("os"), path = require("path");
const { prepare, start, stop } = require("./lib/fixture.cjs");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-7610-"));
const shots = path.resolve(__dirname, "..", "build", "screenshots");
fs.mkdirSync(shots, { recursive: true });
prepare(tmp);
const PORT = 8831;
(async () => {
  let browser;
  try {
    // The driver read the model name and nothing else: no firmware, no telemetry, no probed personal data store.
    start(tmp, "7610", "", PORT, { identity_only: true });
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}),
      args: ["--no-sandbox"],
    });
    const open = async (lang, width, hash = "#phone/overview") => {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      await context.addInitScript(([l]) => { localStorage.setItem("symport-language", l); localStorage.setItem("symport-mode", "developer"); }, [lang]);
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      page.errors = [];
      page.on("pageerror", (e) => page.errors.push(e.message));
      for (let i = 0; i < 60; i++) { try { await page.goto(`http://127.0.0.1:${PORT}/next/${hash}`); break; } catch { await new Promise((r) => setTimeout(r, 250)); } }
      await page.locator("main").waitFor();
      return page;
    };
    const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);

    // 1. Overview: own model, platform, geometry and artwork; nothing invented.
    let page = await open("en", 1366);
    await page.getByRole("heading", { name: "Nokia 7610" }).first().waitFor();
    const main = page.locator("main");
    const text = await main.innerText();
    assert(/Symbian 7\.0s/.test(text) && /S60 2nd/.test(text) && /176×208/.test(text), text);
    assert(!/Supernova/i.test(text));
    const art = await page.locator(".k-identity-media img").getAttribute("src");
    assert(art.includes("phones/nokia-7610"), "own artwork: " + art);
    await page.waitForFunction(() => { const i = document.querySelector(".k-identity-media img"); return i && i.complete && i.naturalWidth > 0; });
    assert(!/(Battery level|Signal strength)/.test(text), "no battery or signal card without telemetry");
    assert(!/\b\d+%/.test(text), "no percentage is drawn: " + text.match(/\b\d+%/));
    assert(/No data|Not reported/.test(text), "missing values say so");
    assert(await noOverflow(page), "overflow on overview");
    await page.screenshot({ path: path.join(shots, "nokia-7610-overview.png"), fullPage: true });

    // 2. The device card in the sidebar uses the same artwork.
    assert((await page.locator(".phone-card img, .sidebar img[src*='nokia-7610']").first().getAttribute("src")).includes("nokia-7610"));

    // 3. Personal data: not an empty list, an explanation.
    await page.evaluate(() => { location.hash = "#phone/contacts"; });
    await page.getByRole("heading", { name: "Contacts", level: 1 }).waitFor();
    const contacts = await page.locator("#page-phone-contacts").innerText();
    assert(!/No contacts|0 contacts/i.test(contacts), contacts);
    assert(/does not expose this phone store|not.*tested|unsupported/i.test(contacts), contacts);

    // 4. Files: no mounted volume is not an empty folder.
    await page.evaluate(() => { location.hash = "#phone/files"; });
    await page.getByRole("heading", { name: "File manager", level: 1 }).waitFor();
    const files = await page.locator("#page-phone-files").innerText();
    assert(!/Folder is empty|Empty folder/i.test(files), files);

    // 5. Recovery wizards are built for S60 3rd and later: the platform check says so.
    await page.evaluate(() => { location.hash = "#revive/network"; });
    const connection = page.locator("#page-revive-network select").first();
    await connection.selectOption({ label: await connection.locator("option", { hasText: "Nokia 7610" }).first().innerText() });
    await page.waitForFunction(() => document.querySelector('#page-revive-network [data-check="platform"]')?.dataset.status === "unsupported");
    const platform = page.locator('#page-revive-network [data-check="platform"]').first();
    assert.equal(await platform.getAttribute("data-status"), "unsupported");
    assert(/S60 2nd Edition/.test(await platform.innerText()));
    await page.close();

    // 6. Theme Studio lists the model like N97 mini, N8 and E7 but refuses it with a reason.
    page = await open("en", 1366, "#personalize/theme-editor");
    await page.getByRole("heading", { name: /Theme/, level: 1 }).first().waitFor();
    const studio = page.locator("#page-personalize-theme-editor");
    const profile = studio.locator("select").filter({ hasText: "Nokia 7610" }).first();
    await profile.selectOption({ label: await profile.locator("option", { hasText: "Nokia 7610" }).first().innerText() });
    await studio.getByText(/Themes for S60 2nd Edition .* are not supported/).first().waitFor();
    assert(await studio.getByRole("button", { name: /^Create editable/ }).isDisabled(), "no theme can be created for the 7610");
    await page.close();

    // 7. Russian and a phone screen.
    page = await open("ru", 390);
    await page.getByRole("heading", { name: "Nokia 7610" }).first().waitFor();
    const ru = await page.locator("main").innerText();
    assert(/Symbian 7\.0s/.test(ru) && /S60 2nd/.test(ru) && /Нет данных|Не сообщается/.test(ru), ru);
    assert(await noOverflow(page), "overflow on the phone layout");
    assert.deepEqual(page.errors, []);
    await page.screenshot({ path: path.join(shots, "nokia-7610-overview-390.png"), fullPage: true });
    await page.close();
    console.log("PASS Nokia 7610: own identity/artwork/platform, no invented telemetry or stores, honest Contacts/Files/Recovery states, no theme profile, RU/mobile");
  } finally {
    if (browser) await browser.close();
    stop();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => { console.error(e); process.exit(1); });
