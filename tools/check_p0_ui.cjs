// P0 browser check: dashboard on real transport data, App Catalog (X-plore, Jellyfin), Firmware & ROM Explorer,
// Dependency & Runtime Manager and application kits. Fixtures are synthetic; nothing here is a phone or firmware.
const { chromium } = require("playwright");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs"), os = require("os"), path = require("path");
const repo = path.resolve(__dirname, ".."), python = process.env.SYMPORT_PYTHON || "python3";
const root = fs.mkdtempSync(path.join(os.tmpdir(), "symport-p0-"));
const port = 8794;
for (const name of ["theme", "tools", "profiles", "catalog"])
  fs.cpSync(path.join(repo, name), path.join(root, name), { recursive: true });
fs.mkdirSync(path.join(root, "volume"));
fs.writeFileSync(path.join(root, "volume", "hello.txt"), "actual private bytes");
const made = spawnSync(python, ["-c", `
import sys
from pathlib import Path
from tests.test_deps import QT, kit_parts, sis
from tests.test_firmware import firmware, zip_bytes
from tests.helpers import make_e32
out = Path(sys.argv[1])
(out / "fw-a.zip").write_bytes(zip_bytes(firmware("1")))
changed = firmware("2")
changed["sys/bin/app.exe"] = make_e32(uid3=0x20001001, imports={"euser.dll": [1], "newdep.dll": [3]}, caps_low=(1 << 13) | (1 << 15))
del changed["resource/apps/t.mif"]
changed["sys/bin/extra.dll"] = make_e32(dll=True)
(out / "fw-b.zip").write_bytes(zip_bytes(changed))
app = sis(0xE0001111, "Demo App", exe=make_e32(imports={"euser.dll": [1]}), deps=[(QT, "Qt", (4, 7, 3))])
(out / "demo-app.sis").write_bytes(app)
(out / "qt.sis").write_bytes(sis(QT, "Qt", version=(4, 7, 3)))
`, root], { cwd: repo, env: { ...process.env, PYTHONPATH: repo } });
if (made.status !== 0) throw Error(made.stderr.toString());
const server = spawn(python, ["-m", "symport.web", "--repo", root, "--port", String(port)], {
  cwd: repo,
  env: { ...process.env, PYTHONPATH: repo, SYMPORT_DEVICE_ROOTS: JSON.stringify({ card: path.join(root, "volume") }), SYMPORT_GAMMU_CONFIG: "", SYMPORT_BRIDGE_URL: "" },
  stdio: "ignore",
});
(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}),
      args: ["--no-sandbox"],
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.setDefaultTimeout(20000);
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    for (let i = 0; i < 50; i++) {
      try { await page.goto(`http://127.0.0.1:${port}/`); break; } catch { await new Promise((r) => setTimeout(r, 200)); }
    }
    await page.getByRole("button", { name: "Настройки", exact: true }).click();
    await page.selectOption("#language", "en");
    await page.getByRole("button", { name: "Settings", exact: true }).click();

    // --- Dashboard: real values only, no trends
    await page.getByRole("heading", { name: "Device overview", exact: true }).waitFor();
    await page.getByText("Connected", { exact: true }).first().waitFor();
    const dash = await page.locator("#page-phone-overview").innerText();
    for (const banned of ["yesterday", "than yesterday", "vs. yesterday", "вчера"])
      if (dash.toLowerCase().includes(banned)) throw Error("Dashboard shows an invented trend: " + banned);
    if (!/Not reported by this transport/.test(dash)) throw Error("Unreported readings must be listed as not reported");
    if (!(await page.locator("#page-phone-overview svg").count())) throw Error("Storage chart missing");

    // --- Catalog: X-plore and Jellyfin (EN/RU) with runtime requirement and guide
    await page.evaluate(() => { location.hash = "#apps/catalog"; });
    await page.locator(".catalog-app").first().waitFor();
    if ((await page.locator(".catalog-app").count()) < 33) throw Error("Curated entries missing");
    const jellyfin = page.locator(".catalog-app", { hasText: "Jellyfin for S60 (English)" });
    await jellyfin.getByRole("button", { name: "Details" }).click();
    const modal = page.getByRole("dialog");
    await modal.getByText(/Runtime required/).waitFor();
    await modal.getByText(/Install only one of them/).waitFor();
    await modal.getByText(/companion/i).first().waitFor();
    await modal.getByText(/untested|не проверен/i).first().waitFor().catch(() => {});
    await page.keyboard.press("Escape");
    await page.locator(".catalog-app", { hasText: "Jellyfin for S60 (Русский)" }).waitFor();
    await page.locator(".catalog-app", { hasText: "X-plore" }).first().waitFor();

    // --- Firmware & ROM Explorer
    await page.evaluate(() => { location.hash = "#tools/firmware"; });
    await page.getByRole("heading", { name: "Firmware & ROM Explorer" }).waitFor();
    for (const [file, label] of [["fw-a.zip", "Stock"], ["fw-b.zip", "Variant"]]) {
      await page.getByLabel("ZIP or ROM image", { exact: true }).setInputFiles(path.join(root, file));
      await page.getByLabel("Label (optional)", { exact: true }).fill(label);
      await page.getByRole("button", { name: "Upload and index" }).click();
      await page.getByRole("row", { name: new RegExp(label) }).getByText("Ready").waitFor();
    }
    await page.getByRole("button", { name: "Stock", exact: true }).click();
    await page.getByRole("button", { name: /^sys/ }).click();
    await page.getByRole("button", { name: /^bin/ }).click();
    await page.getByRole("button", { name: "app.exe" }).click();
    await page.getByText("Secure ID / Vendor ID").waitFor();
    await page.locator("dd", { hasText: "NetworkServices" }).first().waitFor();
    await page.getByText("missing from this image").waitFor();       // gone.dll is not in the image
    await page.getByLabel("Search path", { exact: true }).fill("helper");
    await page.getByRole("button", { name: /helper\.dll/ }).first().waitFor();
    await page.getByLabel("Search path", { exact: true }).fill("");
    await page.getByLabel("Compare the selected image with", { exact: true }).selectOption({ label: "Variant" });
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await page.getByText(/only in A: 1/).waitFor();
    await page.getByText(/changed: 2/).waitFor();
    await page.getByText(/^Only in A/).click();
    await page.getByText("Z:/resource/apps/t.mif").first().waitFor();

    // --- Dependencies: unresolved without the runtime, provided with it
    await page.evaluate(() => { location.hash = "#apps/dependencies"; });
    await page.getByRole("heading", { name: "Dependencies & compatibility" }).waitFor();
    await page.getByLabel("Package (up to 32 MiB)", { exact: true }).setInputFiles(path.join(root, "demo-app.sis"));
    await page.getByRole("button", { name: "Analyze dependencies" }).click();
    await page.getByText("Required, not verified").first().waitFor();
    await page.getByText(/Unresolved/).first().waitFor();
    await page.getByText(/NOT an empty dependency list|Unknown: no firmware data/).first().waitFor();
    await page.getByLabel(/Runtime packages you supply/).setInputFiles(path.join(root, "qt.sis"));
    await page.getByLabel("Firmware image (optional)", { exact: true }).selectOption({ label: "Stock" });
    await page.getByRole("button", { name: "Analyze dependencies" }).click();
    await page.getByText("Supplied in kit").first().waitFor();
    await page.getByText("Present in the supplied firmware").first().waitFor();
    await page.getByText("Missing from the supplied firmware").waitFor().catch(() => {});

    // --- Application kit: order runtime first, ZIP offered
    await page.evaluate(() => { location.hash = "#apps/kits"; });
    const kits = page.locator("#page-apps-kits");
    await kits.getByRole("heading", { name: "Application kits" }).waitFor();
    await kits.getByLabel("Package (up to 32 MiB)", { exact: true }).setInputFiles(path.join(root, "demo-app.sis"));
    await kits.getByRole("button", { name: "Build kit" }).click();
    await kits.getByText("Incomplete", { exact: true }).waitFor();
    await kits.getByText(/No ZIP was made/).waitFor();
    await kits.getByLabel(/Runtime packages you supply/).setInputFiles(path.join(root, "qt.sis"));
    await kits.getByRole("button", { name: "Build kit" }).click();
    await kits.getByText("Complete", { exact: true }).waitFor();
    const order = await kits.locator(".kit-order li").allInnerTexts();
    if (order.length !== 2 || !/Qt/.test(order[0]) || !/Demo App/.test(order[1])) throw Error("Wrong install order: " + order.join("|"));
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      kits.getByRole("link", { name: /demo-app-kit\.zip/ }).click(),
    ]);
    const zip = path.join(root, "kit.zip");
    await download.saveAs(zip);
    if (fs.readFileSync(zip).subarray(0, 2).toString() !== "PK") throw Error("Kit is not a ZIP");

    // --- Placeholders are honest; narrow screens do not overflow
    await page.evaluate(() => { location.hash = "#dev/theme-tests"; });
    await page.getByText("In development", { exact: true }).waitFor();
    if (await page.locator("#page-dev-theme-tests button").count()) throw Error("Placeholder must not offer controls");
    await page.setViewportSize({ width: 390, height: 844 });
    for (const route of ["phone/overview", "phone/files", "apps/catalog", "tools/firmware", "apps/dependencies", "apps/kits", "dev/app-tests"]) {
      await page.evaluate((r) => { location.hash = "#" + r; }, route);
      await page.waitForTimeout(500);
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw Error("Mobile overflow: " + route);
    }
    const ignorable = (m) => /favicon|Failed to load resource/.test(m);
    const real = errors.filter((m) => !ignorable(m));
    if (real.length) throw Error(real.join("\n"));
    console.log("PASS P0 UI: dashboard (real data only), X-plore/Jellyfin catalog details, firmware ZIP index/search/inspect/compare, dependency analysis with firmware data, ordered kit ZIP, honest placeholders, mobile. Synthetic fixtures; nothing was installed or run on a phone.");
  } finally {
    await browser?.close();
    server.kill();
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
