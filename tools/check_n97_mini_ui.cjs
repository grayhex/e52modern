// Actual React/Python/files/PIM flow with a stateful test-only Gammu boundary; no handset claims.
const { chromium } = require("playwright"),
  { spawn } = require("child_process");
const fs = require("fs"),
  os = require("os"),
  path = require("path"),
  assert = require("node:assert/strict");
const repo = path.resolve(__dirname, ".."),
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-mini-"));
const out = path.resolve(
  process.argv[2] || path.join(repo, "build/screenshots/n97-mini"),
);
fs.mkdirSync(out, { recursive: true });
const script = `import sys,os,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from tests.test_device_workspace import MockPhone
from tests.test_deps import sis
from tests.helpers import make_e32
from symport.web import Workbench,make_handler
from symport.phone.local import LocalTransports
from symport.phone import capabilities,gammu_native
root=Path(sys.argv[1]);volume=root/'mass-memory';volume.mkdir()
(volume/'hello.txt').write_text('Actual fixture file',encoding='utf-8')
Image.new('RGB',(640,360),'#124191').save(volume/'sample.jpg')
(root/'sample.sis').write_bytes(sis(0xE0001111,'Mini fixture',platforms=(0x1028315F,),exe=make_e32(imports={'euser.dll':[1]})))
(root/'third.sis').write_bytes(sis(0xE0001111,'Third edition fixture',platforms=(0x102752AE,)))
cfg=root/'gammurc';cfg.write_text('[gammu]\\ndevice=TEST-ONLY\\nconnection=at\\n')
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'mass-memory':str(volume)}),SYMPORT_GAMMU_CONFIG=str(cfg),SYMPORT_CONNECTIONS_FILE='',SYMPORT_BRIDGE_URL='',SYMPORT_MGO_URL='')
w=Workbench(root);local=LocalTransports(root);phone=MockPhone()
phone.identity.update(model='Nokia N97mini',manufacturer='Nokia',firmware=None,rm=None,battery=None,signal=None)
phone.records['contacts'][0]['Entries'][0]['Value']='Synthetic mini contact'
original=phone.invoke
def invoke(config,action,**data):
 result=original(config,action,**data)
 if action=='details':
  result['capability_status']['sms']={'status':'unavailable','reason':'ERR_NOTSUPPORTED'}
 return result
local.gammu.personal.invoke=invoke;gammu_native.available=lambda:True
w.devices.transport=local
server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(w));print(server.server_port,flush=True);server.serve_forever()`;
const child = spawn(
  process.env.SYMPORT_PYTHON || "python3",
  ["-c", script, tmp],
  {
    cwd: repo,
    env: { ...process.env, PYTHONPATH: repo },
    stdio: ["ignore", "pipe", "inherit"],
  },
);
const port = new Promise((resolve, reject) => {
  child.stdout.once("data", (b) => resolve(Number(b.toString().trim())));
  child.once("exit", (c) => reject(Error("Fixture exited " + c)));
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
      reducedMotion: "reduce",
    });
    page.setDefaultTimeout(18000);
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() =>
      localStorage.setItem("symport-language", "en"),
    );
    const route = async (value) => {
      await page.goto(base + "/#" + value);
      return page.locator('[data-route="' + value.split("?")[0] + '"]');
    };
    for (const width of [390, 768, 1366]) {
      await page.setViewportSize({ width, height: 900 });
      const home = await route("phone/overview");
      await home
        .getByRole("heading", { name: "Nokia N97 mini", exact: true })
        .waitFor();
      await home
        .getByRole("img", { name: "Generic phone illustration" })
        .waitFor();
      assert((await home.innerText()).includes("640×360"));
      assert((await home.innerText()).includes("9.4"));
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      await page.screenshot({
        path: path.join(out, "overview-" + width + ".png"),
        fullPage: true,
      });
    }
    const post = async (endpoint, body) =>
      page.evaluate(
        async ([endpoint, body]) => {
          const token = document.querySelector(
            "meta[name=symport-token]",
          ).content;
          const r = await fetch(endpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Symport-Token": token,
            },
            body: JSON.stringify(body),
          });
          return { status: r.status, body: await r.json() };
        },
        [endpoint, body],
      );
    let contacts = await route("phone/contacts");
    await contacts
      .getByLabel("Connection", { exact: true })
      .selectOption("gammu");
    await contacts
      .getByRole("button", { name: "Read phone", exact: true })
      .click();
    await contacts
      .getByLabel("name: Synthetic mini contact", { exact: true })
      .waitFor();
    await contacts
      .getByRole("button", { name: "Export VCF", exact: true })
      .click();
    const download = contacts.getByRole("link", { name: /Download.*vcf/ });
    await download.waitFor();
    const href = await download.getAttribute("href");
    assert(
      Buffer.from(href.split(",")[1], "base64")
        .toString()
        .includes("BEGIN:VCARD"),
    );
    await page.screenshot({
      path: path.join(out, "contacts.png"),
      fullPage: true,
    });
    const sms = await route("phone/messages");
    assert(
      await sms
        .getByRole("button", { name: "Read phone", exact: true })
        .isDisabled(),
    );
    assert((await sms.innerText()).includes("ERR_NOTSUPPORTED"));
    const calendar = await route("phone/calendar");
    await calendar
      .getByRole("button", { name: "Read phone", exact: true })
      .click();
    await calendar
      .getByRole("cell", { name: "Private appointment", exact: true })
      .waitFor();
    await calendar
      .getByRole("button", { name: "Export ICS", exact: true })
      .click();
    await calendar.getByRole("link", { name: /Download.*ics/ }).waitFor();
    await calendar.getByLabel("Store", { exact: true }).selectOption("tasks");
    await calendar
      .getByRole("button", { name: "Read phone", exact: true })
      .click();
    await calendar
      .getByRole("cell", { name: "Private task", exact: true })
      .waitFor();
    // The existing file manager uses an explicitly selected volume, never the Mini identity as a path.
    const files = await route("phone/files");
    await files
      .getByLabel("Connection", { exact: true })
      .selectOption("mass-memory");
    await files.getByText("hello.txt", { exact: true }).first().waitFor();
    const listed = await post("/api/manager", {
      action: "list",
      device: "mass-memory",
      path: "",
    });
    assert.equal(listed.status, 200);
    assert(listed.body.entries.some((e) => e.name === "hello.txt"));
    const copied = await post("/api/manager", {
      action: "download",
      device: "mass-memory",
      path: "hello.txt",
    });
    assert.equal(
      Buffer.from(copied.body.content, "base64").toString(),
      "Actual fixture file",
    );
    const pim = await post("/api/manager", {
      action: "personal-read",
      device: "mass-memory",
      domain: "contacts",
    });
    assert(pim.status >= 400);
    await page.screenshot({
      path: path.join(out, "files.png"),
      fullPage: true,
    });
    const inspector = await route("tools/certificates?profile=nokia-n97-mini");
    await inspector.getByLabel("Model profile", { exact: true }).waitFor();
    assert.equal(
      await inspector.getByLabel("Symbian", { exact: true }).inputValue(),
      "9.4",
    );
    await inspector
      .getByLabel("Package (up to 32 MiB)", { exact: true })
      .setInputFiles(path.join(tmp, "sample.sis"));
    await inspector
      .getByRole("button", { name: "Analyze package", exact: true })
      .click();
    await inspector
      .getByRole("heading", { name: "sample.sis", exact: true })
      .waitFor();
    const reports = await post("/api/inspector", { action: "list" });
    assert.equal(reports.body.reports[0].compatibility, "unknown");
    assert.equal(
      reports.body.reports[0].dependency_analysis.platform_verdict,
      "supported-static",
    );
    await inspector
      .getByLabel("Package (up to 32 MiB)", { exact: true })
      .setInputFiles(path.join(tmp, "third.sis"));
    await inspector
      .getByRole("button", { name: "Analyze package", exact: true })
      .click();
    await inspector
      .getByRole("heading", { name: "third.sis", exact: true })
      .waitFor();
    await inspector
      .getByText("incompatible", { exact: true })
      .first()
      .waitFor();
    await page.screenshot({
      path: path.join(out, "inspector.png"),
      fullPage: true,
    });
    const catalog = await route("apps/catalog");
    await catalog
      .getByLabel("Target profile", { exact: true })
      .selectOption("nokia-n97-mini");
    const cats = await post("/api/catalog", { action: "list" });
    assert(
      cats.body.apps.every(
        (a) => a.model_compatibility["nokia-n97-mini"].status !== "verified",
      ),
    );
    for (const width of [390, 768, 1366]) {
      await page.setViewportSize({ width, height: 900 });
      const theme = await route(
        "personalize/theme-editor?profile=nokia-n97-mini",
      );
      await theme.getByText("Not supported yet", { exact: true }).waitFor();
      assert(
        await theme
          .getByRole("button", {
            name: "Create editable CLEAR theme",
            exact: true,
          })
          .isDisabled(),
      );
      assert(
        await theme
          .getByLabel("Import SIS theme (8 MiB)", { exact: true })
          .isDisabled(),
      );
      assert.equal(
        await theme
          .getByRole("img", { name: /Schematic theme preview/ })
          .count(),
        0,
      );
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      );
      await page.screenshot({
        path: path.join(out, "themes-unavailable-" + width + ".png"),
        fullPage: true,
      });
    }
    const rejected = await post("/api/theme-studio", {
      action: "create",
      profile: "nokia-n97-mini",
      name: "Blocked",
    });
    assert(rejected.status >= 400);
    assert(/S60 5th/.test(rejected.body.error));
    const ru = await browser.newPage({ viewport: { width: 390, height: 900 } });
    await ru.addInitScript(() =>
      localStorage.setItem("symport-language", "ru"),
    );
    await ru.goto(base + "/#personalize/theme-editor?profile=nokia-n97-mini");
    await ru.getByText("Пока не поддерживается", { exact: true }).waitFor();
    await ru.screenshot({
      path: path.join(out, "themes-unavailable-ru.png"),
      fullPage: true,
    });
    const empty = await browser.newPage({
      viewport: { width: 390, height: 900 },
    });
    await empty.addInitScript(() =>
      localStorage.setItem("symport-language", "en"),
    );
    await empty.route("**/api/manager", async (route) => {
      const body = route.request().postDataJSON();
      if (body.action === "discover")
        return route.fulfill({
          json: {
            devices: [],
            models: JSON.parse(
              fs.readFileSync(
                path.join(repo, "symport/phone/device_models.json"),
                "utf8",
              ),
            ).models,
            limitations: {},
          },
        });
      return route.continue();
    });
    await empty.goto(base + "/#phone/overview");
    await empty.getByRole("heading", { name: /No phone connected/ }).waitFor();
    await empty.screenshot({
      path: path.join(out, "empty-state.png"),
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    console.log(
      "PASS N97 mini: 390/768/1366 dashboard/generic artwork, native PIM read+exports, unavailable SMS, actual enrolled-volume files, 5th vs 3rd Inspector, catalog and RU/EN blocked themes. Explicit synthetic adapter; no hardware claim.",
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
