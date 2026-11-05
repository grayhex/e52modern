// Real React/Python integration, synthetic identities only. Never a physical-device test.
// SYMPORT_PYTHON=... SYMPORT_BROWSER_EXECUTABLE=... node tools/check_n95_ui.cjs [screenshots]
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs"),
  os = require("os"),
  path = require("path"),
  assert = require("node:assert/strict");
const repo = path.resolve(__dirname, ".."),
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-n95-"));
const shots = path.resolve(
  process.argv[2] || path.join(repo, "build/screenshots/n95"),
);
fs.mkdirSync(shots, { recursive: true });
const identity = path.join(tmp, "identity.json");
const registry = JSON.parse(
  fs.readFileSync(path.join(repo, "symport/phone/device_models.json"), "utf8"),
);
const models = Object.fromEntries(registry.models.map((p) => [p.id, p]));
fs.writeFileSync(
  identity,
  JSON.stringify({ model: "Nokia N95-1", rm: "RM-159" }),
);
const script = `import sys,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench,make_handler
from tests.capfake import row
root=Path(sys.argv[1])
from tests.test_deps import sis
(root/'fp2.sis').write_bytes(sis(0xE0001111,'FP2 test'))
class Transport:
 def devices(self):
  observed=json.loads((root/'identity.json').read_text())
  return [row(dict(id='test-phone',name=observed['model'],transport='gammu',connected=True,firmware=None,battery=None,signal=None,**observed),available=['identity.read'])]
 def execute(self,data):
  raise ValueError('Synthetic read-only identity transport; no hardware')
w=Workbench(root)
w.devices.transport=Transport()
s=ThreadingHTTPServer(('127.0.0.1',0),make_handler(w))
print(s.server_port,flush=True)
s.serve_forever()`;
const child = spawn(
  process.env.SYMPORT_PYTHON || "python3",
  ["-c", script, tmp],
  {
    cwd: repo,
    env: {
      ...process.env,
      PYTHONPATH: repo,
      SYMPORT_GAMMU_CONFIG: "",
      SYMPORT_BRIDGE_URL: "",
      SYMPORT_DEVICE_ROOTS: "{}",
      SYMPORT_CONNECTIONS_FILE: "",
      SYMPORT_MGO_URL: "",
    },
    stdio: ["ignore", "pipe", "inherit"],
  },
);
const port = new Promise((resolve, reject) => {
  child.stdout.once("data", (b) => resolve(Number(b.toString().trim())));
  child.once("exit", (c) => reject(Error("Fixture server exited: " + c)));
});
(async () => {
  let browser;
  try {
    const base = "http://127.0.0.1:" + (await port);
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE
        ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE }
        : {}),
      args: ["--no-sandbox"],
    });
    const page = await browser.newPage({
      viewport: { width: 1366, height: 900 },
      deviceScaleFactor: 1,
    });
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() =>
      localStorage.setItem("symport-language", "en"),
    );
    for (const [id, model, rm] of [
      ["nokia-n95", "Nokia N95-1", "RM-159"],
      ["nokia-n95-8gb", "Nokia N95", "RM-320"],
    ]) {
      fs.writeFileSync(identity, JSON.stringify({ model, rm }));
      for (const width of [390, 768, 1366]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(base + "/#phone/overview");
        await page.reload();
        await page
          .getByRole("heading", { name: models[id].name, exact: true })
          .waitFor();
        const hero = page.locator('main img[src$="' + models[id].image + '"]');
        await hero.waitFor();
        await page.waitForFunction(() =>
          [...document.images].every((i) => i.complete && i.naturalWidth > 0),
        );
        assert(
          await page
            .locator("body")
            .innerText()
            .then((s) => s.includes("9.2")),
          "FP1 OS not shown",
        );
        assert(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          "Horizontal page overflow",
        );
        await page.screenshot({
          path: path.join(shots, id + "-" + width + ".png"),
          fullPage: true,
        });
      }
    }
    fs.writeFileSync(
      identity,
      JSON.stringify({ model: "Nokia N95", rm: null }),
    );
    await page.goto(base + "/#phone/overview");
    await page.reload();
    await page
      .getByRole("heading", { name: /N95.*variant/i })
      .first()
      .waitFor();
    await page
      .locator('main img[src$="/phones/nokia-n95-family.svg"]')
      .waitFor();
    await page.waitForFunction(() =>
      [...document.images].every((i) => i.complete && i.naturalWidth > 0),
    );
    const russian = await browser.newPage({
      viewport: { width: 390, height: 900 },
    });
    await russian.addInitScript(() =>
      localStorage.setItem("symport-language", "ru"),
    );
    await russian.goto(base + "/#phone/overview");
    await russian
      .getByRole("heading", {
        name: "Nokia N95 (модификация не определена)",
        exact: true,
      })
      .waitFor();
    await russian.screenshot({
      path: path.join(shots, "n95-unknown-ru.png"),
      fullPage: true,
    });
    await russian.close();
    // Exact target selectors, actual upload, real Inspector and FP2 rejection.
    await page.goto(base + "/#tools/certificates?profile=nokia-n95-8gb");
    const inspector = page.locator('[data-route="tools/certificates"]');
    await inspector.getByLabel("Model profile", { exact: true }).waitFor();
    assert.equal(
      await inspector.getByLabel("Symbian", { exact: true }).inputValue(),
      "9.2",
    );
    assert.equal(
      await inspector.getByLabel("Model profile", { exact: true }).inputValue(),
      "nokia-n95-8gb",
    );
    await inspector.locator('img[src="/phones/nokia-n95-8gb.png"]').waitFor();
    await inspector
      .getByLabel("Package (up to 32 MiB)", { exact: true })
      .setInputFiles(path.join(tmp, "fp2.sis"));
    await inspector
      .getByRole("button", { name: "Analyze package", exact: true })
      .click();
    await inspector
      .getByText("incompatible", { exact: true })
      .first()
      .waitFor();
    const report = await page.evaluate(async () => {
      const token = document.querySelector("meta[name=symport-token]").content;
      const list = await fetch("/api/catalog", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Symport-Token": token,
        },
        body: JSON.stringify({ action: "list" }),
      });
      return list.json();
    });
    assert(
      report.apps.every(
        (a) => a.model_compatibility["nokia-n95"].status !== "verified",
      ),
      "Legacy E52 evidence promoted to N95",
    );
    await page.goto(base + "/#apps/catalog");
    const catalog = page.locator('[data-route="apps/catalog"]');
    await catalog
      .getByLabel("Target profile", { exact: true })
      .selectOption("nokia-n95");
    await page.screenshot({
      path: path.join(shots, "catalog-n95.png"),
      fullPage: true,
    });
    await page.goto(base + "/#personalize/theme-editor");
    const studio = page.locator('[data-route="personalize/theme-editor"]');
    for (const id of ["nokia-n95", "nokia-n95-8gb"]) {
      await studio
        .getByLabel("Screen profile", { exact: true })
        .selectOption(id);
      await studio
        .getByRole("button", { name: "Create editable CLEAR theme" })
        .click();
      await studio
        .getByRole("group", { name: models[id].name, exact: true })
        .waitFor();
      await studio
        .getByRole("img", { name: "Schematic theme preview 240×320" })
        .waitFor();
      await page.screenshot({
        path: path.join(shots, "theme-" + id + ".png"),
        fullPage: true,
      });
    }
    // A visual comparison page exists only in the screenshot runner, never in the product UI.
    const compare = await browser.newPage({
      viewport: { width: 1366, height: 760 },
      deviceScaleFactor: 1,
    });
    await compare.setContent(
      '<html lang="en"><style>body{margin:0;background:#f4f7fb;color:#172c4e;font:16px Arial}header{padding:32px}h1{margin:0 0 12px;color:#124191}section{display:flex;justify-content:space-evenly}figure{text-align:center;margin:12px}img{height:430px;max-width:240px;object-fit:contain}figcaption{margin:18px 0}small{color:#607089}</style><header><h1>SymPort · Nokia device profiles</h1><small>Illustrations and schematic profiles · no physical phone connected</small></header><section>' +
        ["nokia-e52", "nokia-e72", "nokia-n95", "nokia-n95-8gb"]
          .map((id) => {
            const p = models[id];
            return `<figure><img src="${base + p.image}" alt="${p.name}"><figcaption><b>${p.name}</b><br><small>Symbian ${p.symbian} · S60 ${p.s60}<br>${p.screen.width} × ${p.screen.height}</small></figcaption></figure>`;
          })
          .join("") +
        "</section></html>",
    );
    await compare.waitForFunction(() =>
      [...document.images].every((i) => i.complete && i.naturalWidth > 0),
    );
    await compare.screenshot({
      path: path.join(shots, "nokia-family-comparison.png"),
    });
    await compare.setViewportSize({ width: 1100, height: 650 });
    await compare.setContent(
      "<style>body{margin:24px;background:#f4f7fb;color:#124191;font:16px Arial}section{display:flex;align-items:start;justify-content:space-around}figure{margin:10px;text-align:center}img{object-fit:contain}h1{font-size:24px}</style><h1>N95 artwork · 180 / 240 px · transparent exports</h1><section>" +
        ["nokia-n95", "nokia-n95-8gb"]
          .flatMap((id) =>
            [180, 240].map(
              (w) =>
                `<figure><img src="${base + models[id].image}" style="width:${w}px" alt="${models[id].name}"><figcaption>${models[id].name} · ${w}px</figcaption></figure>`,
            ),
          )
          .join("") +
        "</section>",
    );
    await compare.waitForFunction(() =>
      [...document.images].every((i) => i.complete && i.naturalWidth > 0),
    );
    await compare.screenshot({
      path: path.join(shots, "n95-artwork-180-240.png"),
    });
    assert.deepEqual(errors, []);
    console.log(
      "PASS: distinct N95 identities, unknown variant, PNG/SVG loading, 390/768/1366 layouts, Inspector target, catalog evidence and native Theme Studio preview. Synthetic transport; hardware not tested.",
    );
  } finally {
    if (browser) await browser.close();
    child.kill("SIGTERM");
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
