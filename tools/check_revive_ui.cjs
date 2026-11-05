// SymPort Revive in a real browser against the Python server. Synthetic identities only; never hardware.
// SYMPORT_PYTHON=... SYMPORT_BROWSER_EXECUTABLE=... node tools/check_revive_ui.cjs [screenshots]
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs"),
  os = require("os"),
  path = require("path"),
  assert = require("node:assert/strict");
const repo = path.resolve(__dirname, ".."),
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "symport-revive-"));
const shots = path.resolve(process.argv[2] || path.join(repo, "build/screenshots/revive"));
fs.mkdirSync(shots, { recursive: true });
const identity = path.join(tmp, "identity.json");
fs.writeFileSync(identity, "null");
const script = `import sys,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from symport.web import Workbench,make_handler
from tests.capfake import row
root=Path(sys.argv[1])
import base64,hashlib
from tests.test_deps import sis
class Transport:
 files={}
 def devices(self):
  observed=json.loads((root/'identity.json').read_text())
  if observed is None: return []
  base=dict(id='test-phone',name=observed.get('model'),transport='windows-bridge',connection_kind='usb',connected=True,free=800*1024*1024,total=2*1024**3,**observed)
  return [row(base,available=['identity.read','storage.read','files.list','files.download'],untested_writes=['files.upload','packages.transfer'])]
 def execute(self,data):
  a,p=data['action'],data.get('path','')
  if a=='mkdir': return {}
  if a=='list':
   names=[x.split('/',1)[1] for x in self.files if x.startswith(p+'/')]
   if not names: raise ValueError('no such folder')
   return {'entries':[{'name':n,'directory':False,'size':len(self.files[p+'/'+n])} for n in names]}
  if a=='upload':
   if p in self.files: raise FileExistsError(p)
   self.files[p]=base64.b64decode(data['content']); return {'status':'verified'}
  if a=='download':
   if p not in self.files: raise ValueError('missing')
   return {'content':base64.b64encode(self.files[p]).decode()}
  if a=='delete':
   del self.files[p]; return {}
  raise ValueError('Synthetic transport: '+a)
w=Workbench(root)
w.devices.transport=Transport()
from tests.helpers import make_e32
from symport.sis import writer
(root/'reborn.sis').write_bytes(sis(0xE0009999,'Synthetic Reborn',platforms=(0x102032BE,),exe=make_e32(imports={'euser.dll':[1]}),extra=[writer.SisFile('!:\\\\resource\\\\apps\\\\reborn.rsc',b'rsc')]))
blob=sis(0xE0001234,'Synthetic MBedTLS')
spec=dict(w.revive.tls.components['mbedtls-lib'],size=len(blob),sha256=hashlib.sha256(blob).hexdigest(),package={'uid':'0xe0001234','signed':False,'targets':[]})
w.revive.tls.components=dict(w.revive.tls.components,**{'mbedtls-lib':spec})
w.revive.execute({'action':'tls-import','name':'MBedTLS.sis','content':base64.b64encode(blob).decode()})
w.revive.services.probe=lambda url,hosts:{'ok':True,'status':200,'location':None,'meta_refresh':'https://avalibeyaz.com/s3/connecttest.php' if 'conntest' in url else None}
w.revive.tls.probe=lambda host:{'ok':True,'tls_version':'TLSv1.3','cipher':'TEST','leaf':{'subject':'CN='+host,'issuer':'CN=Synthetic CA','not_before':'Jan  1 00:00:00 2026 GMT','not_after':'Jan  1 00:00:00 2030 GMT'}}
s=ThreadingHTTPServer(('127.0.0.1',0),make_handler(w))
print(s.server_port,flush=True)
s.serve_forever()`;
const child = spawn(process.env.SYMPORT_PYTHON || "python3", ["-c", script, tmp], {
  cwd: repo,
  env: { ...process.env, PYTHONPATH: repo, SYMPORT_GAMMU_CONFIG: "", SYMPORT_BRIDGE_URL: "", SYMPORT_DEVICE_ROOTS: "{}", SYMPORT_CONNECTIONS_FILE: "", SYMPORT_MGO_URL: "" },
  stdio: ["ignore", "pipe", "inherit"],
});
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
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}),
      args: ["--no-sandbox"],
    });
    const open = async (lang, width, hash = "#tools/revive") => {
      const page = await browser.newPage({ viewport: { width, height: 900 }, deviceScaleFactor: 1 });
      page.setDefaultTimeout(15000);
      page.errors = [];
      page.on("pageerror", (e) => page.errors.push(e.message));
      await page.addInitScript((l) => localStorage.setItem("symport-language", l), lang);
      await page.goto(base + "/" + hash);
      return page;
    };
    const overflow = (page) =>
      page.evaluate(() => {
        if (document.documentElement.scrollWidth <= innerWidth) return true;
        const wide = [...document.querySelectorAll("main *")].filter((e) => e.getBoundingClientRect().right > innerWidth + 1);
        return wide.slice(0, 5).map((e) => e.tagName + "." + e.className).join(", ") || "document";
      }).then((r) => (r === true ? true : (console.error("overflowing:", r), false)));

    // 1. No phone: honest empty state with next steps.
    let page = await open("en", 1366);
    await page.getByRole("heading", { name: "SymPort Revive", level: 1 }).waitFor();
    await page.getByRole("heading", { name: "No phone connection" }).waitFor();
    assert(await overflow(page), "overflow in empty state");
    await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
    await page.screenshot({ path: path.join(shots, "empty-en.png"), fullPage: true });
    await page.close();

    // 2. E52 observed through the connection.
    fs.writeFileSync(identity, JSON.stringify({ model: "Nokia E52", rm: null, firmware: "v 081.003" }));
    for (const width of [390, 768, 1366]) {
      page = await open("en", width);
      const model = page.locator('[data-fact="model"]');
      await model.waitFor();
      await page.waitForFunction(() => document.querySelector('[data-fact="model"]')?.textContent.includes("Nokia E52"));
      assert((await model.innerText()).includes("Read from the device"));
      assert((await page.locator('[data-fact="platform"]').innerText()).includes("Documented profile"));
      assert((await page.locator('[data-fact="rights"]').innerText()).includes("Not determined"));
      assert(await overflow(page), "overflow at " + width);
      await page.getByRole("button", { name: /Network and certificates/ }).click();
      await page.locator('[data-op="clock-check"]').waitFor();
      await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
      await page.screenshot({ path: path.join(shots, "e52-" + width + ".png"), fullPage: true });
      await page.close();
    }

    // 2b. TLS revival: matrix, pinned components, diagnostics that say where they ran.
    page = await open("en", 1366);
    await page.locator("#revive-tls").waitFor();
    await page.locator('#revive-tls [data-target="nokia-n97-mini"]').waitFor();
    assert.equal(await page.locator("#revive-tls tbody tr").count(), 5);
    const qt = await page.locator('[data-target="nokia-n95"]').innerText();
    assert(qt.includes("Not applicable") && qt.includes("not tested"), "matrix cells: " + qt);
    const comp = page.locator('[data-component="ssl-patch"]');
    await comp.waitFor();
    assert((await comp.innerText()).includes("62365db422253e87b0328058e160ab03c3a3501e7eeae064596727307be9b416"));
    assert.equal(await comp.getByRole("button", { name: "Copy to phone" }).count(), 0, "no direct copy outside the safety net");
    await page.getByLabel("Date shown on the phone").fill("2010-01-01");
    await page.getByRole("button", { name: "Run diagnostics" }).click();
    const diag = page.getByTestId("tls-diagnose");
    await diag.waitFor();
    const diagText = await diag.innerText();
    assert(diagText.includes("Ran on the SymPort server") && diagText.includes("outside the certificate validity window"), diagText);
    assert(diagText.includes("Ran in the Windows Bridge") && diagText.includes("Not available"));
    // Safety Net: plan -> snapshot -> copy -> postflight -> rollback, all through the server.
    await page.getByRole("button", { name: "Plan safe copy: MBedTLS", exact: true }).click();
    const plan = page.getByTestId("safety-plan");
    await plan.waitFor();
    // The plan view loads after the plan exists; wait for its content instead of reading it at once.
    await plan.getByText("SymPort-TLS/MBedTLS.sis").first().waitFor();
    const confirm = plan.getByLabel("I confirm this step");
    await confirm.check();
    await plan.getByRole("button", { name: "1. Take snapshot" }).click();
    await page.getByTestId("snapshot-kinds").waitFor();
    assert((await page.getByTestId("snapshot-kinds").innerText()).includes("not-available"), "firmware backup must be reported as not available");
    await confirm.check();
    await plan.getByRole("button", { name: "2. Copy files to the phone" }).click();
    await plan.getByText("Transferred, awaiting manual install").first().waitFor();
    await plan.getByRole("button", { name: "3. Postflight (read only)" }).click();
    const post = page.getByTestId("postflight-result");
    await post.waitFor();
    const postText = await post.innerText();
    assert(postText.includes("present-hash-match") && postText.includes("Installation: unknown"), postText);
    await plan.getByRole("button", { name: "Rollback preview" }).click();
    await page.getByTestId("rollback-result").getByText(/Would remove: 1/).waitFor();
    await confirm.check();
    await plan.getByRole("button", { name: "Rollback our files" }).click();
    await page.getByTestId("rollback-result").getByText(/Removed: 1/).waitFor();
    await plan.getByLabel("These are what I saw on the phone").check();
    await plan.getByRole("button", { name: "Problem" }).first().click();
    await plan.getByText(/— fail/).waitFor();
    await plan.getByRole("button", { name: "Export JSON report" }).click();
    await plan.getByRole("link", { name: /symport-safety-/ }).waitFor();
    await page.getByLabel("Application type").selectOption("qt");
    await page.locator('[data-support="not-applicable"]').waitFor();
    assert(await overflow(page), "overflow in TLS section");
    await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
    await page.screenshot({ path: path.join(shots, "tls-1366.png"), fullPage: true });
    await page.close();

    // 2b2. Revive home and legacy services (server probe is replaced by a synthetic one in the fixture).
    page = await open("en", 1366);
    await page.locator("#revive-home").waitFor();
    await page.getByTestId("home-recs").waitFor();
    assert((await page.getByTestId("home-recs").innerText()).includes("Basis"), "recommendations carry their basis");
    await page.locator('[data-shortcut="legacy-services"]').click();
    await page.locator("#revive-services").waitFor();
    const matrix = page.getByTestId("services-matrix");
    await matrix.waitFor();
    assert.equal(await matrix.locator("tbody tr").count(), 14);
    const uaprof = await page.locator('[data-service="reborn-uaprof-n8"]').innerText();
    assert(uaprof.includes("Not supported") && uaprof.includes("Belle"), uaprof);
    assert(!(await matrix.innerText()).includes("Available"), "nothing is marked available without evidence");
    await page.getByRole("button", { name: /Check substitute hosts/ }).click();
    await page.getByTestId("services-diag").waitFor();
    await page.locator('[data-diag="reborn-conntest"]').getByText("matches-registry").waitFor();
    await page.getByLabel("I changed this setting myself on the phone").check();
    await page.getByLabel("Value before").fill("https://old.example/");
    await page.getByLabel("Value after").fill("https://lite.duckduckgo.com");
    await page.getByRole("button", { name: "Record", exact: true }).click();
    await page.getByTestId("services-records").getByText(/Set the value back to: https:\/\/old.example\//).waitFor();
    assert(await overflow(page), "overflow in services");
    await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
    await page.screenshot({ path: path.join(shots, "services-1366.png"), fullPage: true });
    // Add-ons and Patch Manager.
    await page.locator('[data-shortcut="addons"]').click();
    await page.locator("#revive-addons").waitFor();
    await page.locator('[data-addon="tls-mbedtls"][data-decision="ready-to-prepare"]').waitFor();
    const rp = page.locator('[data-addon="rompatcher-debloated"]');
    await rp.waitFor();
    assert.equal(await rp.getAttribute("data-decision"), "blocked");
    assert(await rp.locator('[data-block="licence-missing"]').count() === 1, "unlicensed add-on is blocked with a reason");
    assert((await page.locator('[data-addon="tls-ssl-patch"]').innerText()).includes("closed"), "system patches start closed");
    assert((await page.getByTestId("levels-tls-mbedtls").innerText()).includes("not available (no agent)"));
    await page.getByLabel("Patch name").fill("Patch A");
    await page.getByLabel(/Starts via/).fill("domainsrv");
    await page.getByLabel("State you observed").selectOption("autostart");
    await page.getByRole("button", { name: "Add to inventory" }).click();
    await page.getByTestId("patch-list").getByText(/Patch A — autostart/).waitFor();
    assert((await page.getByTestId("patch-note").innerText()).includes("No agent reads patches"));
    await rp.getByRole("button", { name: "Dry run" }).click();
    await page.getByTestId("plan-rompatcher-debloated").getByText(/autostart-conflict/).waitFor();
    await page.close();

    // 2c. Reborn wizard for an identified N95: import -> pin -> backup statement -> consents -> copy -> user-reported install.
    fs.writeFileSync(identity, JSON.stringify({ model: "Nokia N95-1", rm: "RM-159", firmware: "v 12.0.013" }));
    page = await open("en", 1366);
    await page.getByRole("button", { name: /Reborn preparation for N95/ }).click();
    const reborn = page.locator("#revive-reborn");
    await reborn.waitFor();
    const rtext = await reborn.innerText();
    assert(rtext.includes("v1.00 alpha") && rtext.includes("not stated by the author") && rtext.includes("not published"), rtext);
    assert(rtext.includes("none: the author publishes no hash"));
    await page.waitForFunction(() => document.querySelector('[data-testid="reborn-variant"]')?.dataset.variant === "candidate");
    assert(await reborn.getByRole("button", { name: "Plan safe copy of the pinned file" }).isDisabled(), "no plan without a pinned file");
    await reborn.locator('input[type="file"]').setInputFiles(path.join(tmp, "reborn.sis"));
    const imp = reborn.getByTestId("reborn-import");
    await imp.waitFor();
    assert((await imp.innerText()).includes("high risk"), "system-level components are flagged");
    assert.equal(await imp.getByTestId("reborn-mods").locator("li").count(), 6);
    assert((await imp.getByTestId("reborn-mods").innerText()).includes("not detected"), "absent claims read 'not detected'");
    assert((await imp.getByTestId("reborn-version").innerText()).includes("v1.00 alpha"));
    await reborn.getByLabel("I obtained this exact file from the author").check();
    await reborn.getByRole("button", { name: "Pin this SHA-256" }).click();
    await reborn.getByText("(your pin)").waitFor();
    await reborn.getByLabel("I have a separate copy of the data I care about").check();
    await reborn.getByRole("button", { name: "Record my statement" }).click();
    await reborn.getByText(/Recorded \(your statement/).waitFor();
    // Device-level rights are only the user's own observation.
    await page.getByLabel("Installation rights you observed").selectOption("device");
    await page.getByLabel("This is my own observation").check();
    await page.getByRole("button", { name: "Record rights" }).click();
    await page.waitForFunction(() => document.querySelector('[data-check="rights"]')?.dataset.status === "ready");
    await reborn.getByRole("button", { name: "Plan safe copy of the pinned file" }).click();
    const rplan = reborn.getByTestId("safety-plan");
    await rplan.waitFor();
    await rplan.getByLabel("I confirm this step").check();
    await rplan.getByRole("button", { name: "1. Take snapshot" }).click();
    await rplan.getByTestId("snapshot-kinds").waitFor();
    await rplan.getByLabel("I confirm this step").check();
    await rplan.getByRole("button", { name: "2. Copy files to the phone" }).click();
    await page.getByRole("alert").filter({ hasText: /Blocked/ }).waitFor();
    await rplan.getByLabel("I understand this cannot be undone by SymPort").check();
    await rplan.getByRole("button", { name: "Acknowledge" }).click();
    await rplan.getByLabel("I confirm this step").check();
    await rplan.getByRole("button", { name: "2. Copy files to the phone" }).click();
    await rplan.getByText("Transferred, awaiting manual install").first().waitFor();
    assert.equal(await reborn.getByTestId("reborn-outcome").getAttribute("data-outcome"), "not-confirmed", "a copy is never an installation");
    await reborn.getByLabel("These are my own observations").check();
    await reborn.locator('[data-stage="installed"]').getByRole("button", { name: "Yes" }).click();
    await page.waitForFunction(() => document.querySelector('[data-testid="reborn-outcome"]')?.dataset.outcome === "installed-reported-unchecked");
    assert.equal(await reborn.getByTestId("reborn-postchecks").locator("li").count(), 6);
    await reborn.locator('[data-postcheck="https-on-phone"]').getByRole("button", { name: "No" }).click();
    await reborn.getByText(/https-on-phone|HTTPS opens on the phone — fail \(user-reported\)/).first().waitFor();
    assert(await overflow(page), "overflow in the Reborn wizard");
    await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
    await page.screenshot({ path: path.join(shots, "reborn-1366.png"), fullPage: true });
    await page.close();

    // 3. Manual input stays separate and never raises identity to "ready"; mismatches are visible.
    fs.writeFileSync(identity, JSON.stringify({ model: "N95", rm: "RM-999" }));
    page = await open("en", 1366);
    await page.getByRole("button", { name: /Reborn preparation for N95/ }).click();
    const identityCheck = page.locator('[data-check="identity"]');
    await identityCheck.waitFor();
    assert.equal(await identityCheck.getAttribute("data-status"), "needs-action");
    assert((await page.getByRole("heading", { name: /Typed by you/ }).count()) === 1);
    // On-phone steps need an explicit confirmation before they can be recorded.
    await page.getByRole("button", { name: /Application kit/ }).click();
    const install = page.locator('[data-op="kit-install-manual"]');
    await install.waitFor();
    const record = install.getByRole("button", { name: "Record my observation" });
    assert(await record.isDisabled());
    await install.getByLabel("This is what I saw on the phone").check();
    await page.evaluate(() => window.scrollTo(0, 0)); // sticky sidebar must sit in the corner of the capture
    await page.screenshot({ path: path.join(shots, "n95-unknown-rm.png"), fullPage: true });
    await page.close();

    // 3b. N95 8GB is never assumed to match.
    fs.writeFileSync(identity, JSON.stringify({ model: "N95 8GB", rm: "RM-320", firmware: "v 1" }));
    page = await open("ru", 390);
    await page.getByRole("button", { name: /Подготовка Reborn для N95/ }).click();
    await page.waitForFunction(() => document.querySelector('[data-testid="reborn-variant"]')?.dataset.variant === "blocked");
    assert((await page.getByTestId("reborn-variant").innerText()).includes("не доказана"));
    assert(await overflow(page), "overflow in Russian Reborn");
    await page.close();
    fs.writeFileSync(identity, JSON.stringify({ model: "Nokia E52", rm: null, firmware: "v 081.003" }));

    // 4. Russian, mobile.
    page = await open("ru", 390);
    await page.getByRole("heading", { name: "SymPort Revive", level: 1 }).waitFor();
    await page.getByText("Прочитано с устройства").first().waitFor();
    await page.getByRole("button", { name: /Набор приложений/ }).click();
    await page.locator('[data-op="kit-transfer"]').waitFor();
    assert(await overflow(page), "overflow in Russian mobile");
    await page.getByRole("button", { name: /Сеть и сертификаты/ }).click();
    await page.getByRole("heading", { name: /Возрождение TLS/ }).waitFor();
    await page.getByRole("button", { name: "Запустить диагностику" }).click();
    await page.getByText("Выполнено на сервере SymPort").waitFor();
    await page.getByRole("heading", { name: "Страховка восстановления" }).waitFor();
    assert(await overflow(page), "overflow in Russian mobile TLS");
    assert.deepEqual(page.errors, []);
    await page.close();
    console.log("Revive UI check passed");
  } finally {
    if (browser) await browser.close();
    child.kill();
  }
})().catch((e) => {
  console.error(e);
  child.kill();
  process.exit(1);
});
