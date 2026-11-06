// Real React/Python/filesystem flow; only native handset replies are explicit test doubles.
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs"),
  os = require("os"),
  path = require("path"),
  assert = require("node:assert/strict");
const repo = path.resolve(__dirname, ".."),
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-68-"));
const out = path.resolve(
  process.argv[2] || path.join(repo, "build/screenshots/n8-e7"),
);
fs.mkdirSync(out, { recursive: true });
const script = `import sys,os,json,io,zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from tests.test_device_workspace import MockPhone
from tests.test_deps import sis
from tests.helpers import make_e32
from symport.web import Workbench,make_handler
from symport.phone.local import LocalTransports
from symport.phone.gammu_adapter import GammuAdapter
from symport.phone import gammu_native
root=Path(sys.argv[1]);volumes={}
for ident in ('n8-memory','n8-card','e7-memory'):
 p=root/ident;p.mkdir();(p/'hello.txt').write_text('Actual host-volume fixture',encoding='utf-8');Image.new('RGB',(640,360),'#124191').save(p/'photo.jpg');volumes[ident]=str(p)
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps(volumes),SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_BRIDGE_URL='',SYMPORT_MGO_URL='')
w=Workbench(root);local=LocalTransports(root);local.adapters={};gammu_native.available=lambda:True
for ident,model,rm in [('n8','N8-00','RM-596'),('e7','E7-00','RM-626')]:
 cfg=root/(ident+'.cfg');cfg.write_text('[gammu]\\ndevice=TEST-ONLY\\nconnection=at\\n')
 phone=MockPhone();phone.identity.update(model=model,rm=rm,manufacturer='Nokia',firmware=None,battery=None,signal=None)
 def invoke(config,action,_phone=phone,**kw):
  result=_phone.invoke(config,action,**kw)
  if action=='details':result['capability_status']={d:{'status':'unavailable','reason':'ERR_NOTSUPPORTED'} for d in ('contacts','calendar','tasks','sms')}
  return result
 a=GammuAdapter(root,ident,str(cfg),kind='gammu-usb');a.personal.invoke=invoke;local.adapters[ident]=a
w.devices.transport=local
for name,uid in [('base.sis',0x20022E6D),('belle.sis',0x2003A678),('legacy.sis',0x102752AE)]:
 (root/name).write_bytes(sis(0xE0001111,'Synthetic package',platforms=(uid,)))
(root/'own.vpl').write_text('<VariantPackingList><ProductType>RM-626</ProductType><SwVersion>111.040.fixture</SwVersion><ProductCode>TEST-ONLY</ProductCode><Language>Russian</Language><Keyboard>Russian</Keyboard></VariantPackingList>')
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w') as z:z.writestr('Z/sys/bin/euser.dll',make_e32(dll=True))
(root/'unpacked.zip').write_bytes(buf.getvalue())
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
  child.stdout.once("data", (b) => resolve(Number(String(b).trim())));
  child.once("exit", (c) => reject(Error("Fixture exited " + c)));
});
(async () => {
  let browser, page;
  try {
    const base = "http://127.0.0.1:" + (await port);
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE
        ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE }
        : {}),
      args: ["--no-sandbox"],
    });
    page = await browser.newPage({
      viewport: { width: 1366, height: 900 },
      reducedMotion: "reduce",
    });
    page.setDefaultTimeout(18000);
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.addInitScript(() => {
      localStorage.setItem("symport-language", "en");
      localStorage.setItem("symport-mode", "developer");
    });
    const route = async (r) => {
      await page.goto(base + "/#" + r);
      return page.locator('[data-route="' + r.split("?")[0] + '"]');
    };
    const post = (endpoint, body) =>
      page.evaluate(
        async ([url, data]) => {
          const r = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Symport-Token": document.querySelector(
                "meta[name=symport-token]",
              ).content,
            },
            body: JSON.stringify(data),
          });
          return { status: r.status, body: await r.json() };
        },
        [endpoint, body],
      );
    const noOverflow = async () =>
      assert(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        "Horizontal overflow",
      );
    for (const [id, name, profile, volume] of [
      ["n8", "Nokia N8-00", "nokia-n8", "n8-memory"],
      ["e7", "Nokia E7-00", "nokia-e7", "e7-memory"],
    ]) {
      const identityPage = await route("phone/contacts");
      await identityPage
        .getByLabel("Connection", { exact: true })
        .selectOption(id);
      let files;
      for (const width of [390, 768, 1366]) {
        await page.setViewportSize({ width, height: 900 });
        const home = await route("phone/overview");
        await home.getByRole("heading", { name, exact: true }).waitFor();
        const img = home.getByRole("img", { name, exact: true });
        await img.evaluate(async (image) => image.decode());
        assert((await home.innerText()).includes("OS release not reported"));
        assert(!(await home.innerText()).includes("Symbian Belle"));
        assert(
          await img.evaluate(
            (image) => getComputedStyle(image).objectFit === "contain",
          ),
        );
        await noOverflow();
        await page.screenshot({
          path: path.join(out, id + "-overview-" + width + ".png"),
          fullPage: true,
        });
      }
      if (id === "e7") {
        await page
          .getByRole("button", { name: "Keyboard open", exact: true })
          .click();
        await page
          .getByRole("img", { name, exact: true })
          .evaluate(async (image) => image.decode());
        await noOverflow();
        await page.screenshot({
          path: path.join(out, "e7-open.png"),
          fullPage: true,
        });
      }
      const contacts = await route("phone/contacts");
      assert(
        await contacts
          .getByRole("button", { name: "Read phone", exact: true })
          .isDisabled(),
      );
      assert((await contacts.innerText()).includes("ERR_NOTSUPPORTED"));
      files = await route("phone/files");
      await files
        .getByLabel("Connection", { exact: true })
        .selectOption(volume);
      await files.getByText("hello.txt", { exact: true }).first().waitFor();
      const raw = fs.readFileSync(path.join(tmp, "base.sis"));
      const request = {
        action: "transfer",
        device: volume,
        path: "own.sis",
        content: raw.toString("base64"),
      };
      assert((await post("/api/manager", request)).status >= 400);
      const sent = await post("/api/manager", { ...request, confirm: true });
      assert.equal(sent.body.status, "transferred-not-installed");
      const back = await post("/api/manager", {
        action: "download",
        device: volume,
        path: "own.sis",
      });
      assert(Buffer.from(back.body.content, "base64").equals(raw));
      assert(
        (await post("/api/manager", { ...request, confirm: true })).status >=
          400,
      );
      assert(
        (
          await post("/api/manager", {
            action: "upload",
            device: volume,
            path: "sys/danger.txt",
            content: "eA==",
            confirm: true,
          })
        ).status >= 400,
      );
      const copy = await post("/api/manager", {
        action: "backup",
        device: volume,
        path: "",
      });
      assert(
        copy.body.content &&
          copy.body.scope.includes("subdirectories excluded"),
      );
      const pim = await post("/api/manager", {
        action: "personal-read",
        device: volume,
        domain: "contacts",
      });
      assert(pim.status >= 400);
      const gallery = await route("phone/media");
      await gallery
        .getByLabel("Connection", { exact: true })
        .first()
        .selectOption(volume);
      await gallery
        .getByRole("button", { name: "Read gallery", exact: true })
        .click();
      await gallery
        .getByRole("checkbox", { name: "Select photo.jpg", exact: true })
        .waitFor();
      const inspector = await route("tools/certificates?profile=" + profile);
      const os = inspector.getByLabel("Symbian", { exact: true });
      assert.equal(await os.inputValue(), "");
      await inspector
        .getByLabel("Package (up to 32 MiB)", { exact: true })
        .setInputFiles(path.join(tmp, "belle.sis"));
      await inspector
        .getByRole("button", { name: "Analyze package", exact: true })
        .click();
      await inspector
        .getByRole("heading", { name: "belle.sis", exact: true })
        .waitFor();
      let reports = await post("/api/inspector", { action: "list" });
      assert.equal(
        reports.body.reports[0].dependency_analysis.platform_verdict,
        "unknown",
      );
      await os.fill("Belle Refresh");
      await inspector
        .getByRole("button", { name: "Analyze package", exact: true })
        .click();
      for (let attempt = 0; attempt < 20; attempt++) {
        reports = await post("/api/inspector", { action: "list" });
        if (
          reports.body.reports[0]?.dependency_analysis.platform_verdict ===
          "supported-static"
        )
          break;
        await page.waitForTimeout(100);
      }
      assert.equal(
        reports.body.reports[0].dependency_analysis.platform_verdict,
        "supported-static",
      );
      await inspector
        .getByLabel("Package (up to 32 MiB)", { exact: true })
        .setInputFiles(path.join(tmp, "legacy.sis"));
      await inspector
        .getByRole("button", { name: "Analyze package", exact: true })
        .click();
      await inspector
        .getByRole("heading", { name: "legacy.sis", exact: true })
        .waitFor();
      await inspector
        .getByText("incompatible", { exact: true })
        .first()
        .waitFor();
      await page.screenshot({
        path: path.join(out, id + "-inspector.png"),
        fullPage: true,
      });
      const theme = await route("personalize/theme-editor?profile=" + profile);
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
        (
          await post("/api/theme-studio", {
            action: "create",
            name: "Blocked",
            profile,
          })
        ).status >= 400,
      );
      await page.screenshot({
        path: path.join(out, id + "-themes-unavailable.png"),
        fullPage: true,
      });
      const catalog = await route("apps/catalog");
      await catalog
        .getByLabel("Target profile", { exact: true })
        .selectOption(profile);
      const entries = await post("/api/catalog", { action: "list" });
      assert(
        entries.body.apps.every(
          (a) => a.model_compatibility[profile].status !== "verified",
        ),
      );
      const collection = await post("/api/catalog", {
        action: "collection-save",
        name: "Host fixture " + id,
        profile,
        ids: ["xplore"],
      });
      assert.equal(collection.status, 200);
      const exported = await post("/api/catalog", {
        action: "collection-export",
        id: collection.body.id,
      });
      const imported = await post("/api/catalog", {
        action: "collection-import",
        document: exported.body,
      });
      assert.equal(imported.status, 200);
      const recovery = await post("/api/catalog", {
        action: "recovery-plan",
        id: imported.body.id,
        profile,
      });
      assert.equal(recovery.status, 200);
      assert.equal(recovery.body.target.symbian, null);
    }
    const identityPage = await route("phone/contacts");
    await identityPage
      .getByLabel("Connection", { exact: true })
      .selectOption("e7");
    const revive = await route("revive/home");
    const suggestion = revive.locator('[data-rec="belle-cfw-research"]');
    await suggestion.waitFor();
    await suggestion.getByRole("button", { name: "Open", exact: true }).click();
    await page
      .locator("#cfw-preparation")
      .getByLabel("Model profile", { exact: true })
      .waitFor();
    assert.equal(
      await page
        .locator("#cfw-preparation")
        .getByLabel("Model profile", { exact: true })
        .inputValue(),
      "nokia-e7",
    );
    const cfw = await route("tools/cfw?profile=nokia-e7");
    await cfw
      .getByLabel("VPL manifest (optional, 512 KiB)", { exact: true })
      .setInputFiles(path.join(tmp, "own.vpl"));
    await cfw
      .getByRole("button", {
        name: "Analyze preparation (dry run)",
        exact: true,
      })
      .click();
    await cfw
      .getByRole("link", { name: "Download JSON report", exact: true })
      .waitFor();
    const href = await cfw
      .getByRole("link", { name: "Download JSON report", exact: true })
      .getAttribute("href");
    const report = JSON.parse(
      decodeURIComponent(href.split(",").slice(1).join(",")),
    );
    assert.equal(report.flashing, "unsupported");
    assert.equal(report.package.rm, "RM-626");
    assert.equal(report.package.keyboard, "Russian");
    assert(report.manifest.sha256);
    assert.equal(report.physical_device, "not-tested");
    await noOverflow();
    await page.screenshot({
      path: path.join(out, "e7-cfw-preparation.png"),
      fullPage: true,
    });
    // Exercise the existing binary upload/index and bind that actual image hash into the dry-run report.
    const image = await page.evaluate(
      async ([endpoint, bytes]) => {
        const r = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/octet-stream",
            "X-Symport-Token": document.querySelector(
              "meta[name=symport-token]",
            ).content,
          },
          body: new Uint8Array(bytes),
        });
        return r.json();
      },
      [
        base + "/api/firmware/upload?name=unpacked.zip",
        Array.from(fs.readFileSync(path.join(tmp, "unpacked.zip"))),
      ],
    );
    for (let i = 0; i < 40; i++) {
      const status = await post("/api/firmware", {
        action: "status",
        id: image.id,
      });
      if (status.body.status === "ready") break;
      await page.waitForTimeout(100);
    }
    const bound = await post("/api/firmware", {
      action: "cfw-plan",
      source: "reborn-n8-e7",
      profile: "nokia-e7",
      image: image.id,
      manifest: fs.readFileSync(path.join(tmp, "own.vpl")).toString("base64"),
    });
    assert.equal(bound.status, 200);
    assert(bound.body.image.sha256 && bound.body.image.files > 0);
    await page.setViewportSize({ width: 390, height: 900 });
    await noOverflow();
    const ru = await browser.newPage({ viewport: { width: 390, height: 900 } });
    await ru.addInitScript(() => {
      localStorage.setItem("symport-language", "ru");
      localStorage.setItem("symport-mode", "developer");
    });
    await ru.goto(base + "/#tools/cfw?profile=nokia-e7");
    await ru
      .getByRole("heading", {
        name: "Подготовка N8 / E7 (только чтение)",
        exact: true,
      })
      .waitFor();
    assert(
      await ru.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await ru.screenshot({
      path: path.join(out, "cfw-ru-390.png"),
      fullPage: true,
    });
    await ru.goto(base + "/#phone/connection");
    await ru
      .getByText("Режимы USB на Nokia N8 / E7", { exact: true })
      .waitFor();
    await ru.close();
    assert.deepEqual(errors, []);
    console.log(
      "PASS N8/E7: 390/768/1366 artwork, E7 slider view, OS unknown vs explicit Belle, S60v3 rejection, actual host SIS round-trip/backup/media, PIM probes, disabled themes, VPL+indexed image CFW report, RU/EN. Physical devices: not-tested.",
    );
  } catch (error) {
    if (page)
      await page.screenshot({
        path: path.join(out, "failure.png"),
        fullPage: true,
      });
    throw error;
  } finally {
    await browser?.close();
    child.kill("SIGTERM");
    fs.rmSync(tmp, { recursive: true, force: true });
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
