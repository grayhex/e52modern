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
blob=sis(0xE0001234,'Synthetic MBedTLS')
spec=dict(w.revive.tls.components['mbedtls-lib'],size=len(blob),sha256=hashlib.sha256(blob).hexdigest(),package={'uid':'0xe0001234','signed':False,'targets':[]})
w.revive.tls.components=dict(w.revive.tls.components,**{'mbedtls-lib':spec})
w.revive.execute({'action':'tls-import','name':'MBedTLS.sis','content':base64.b64encode(blob).decode()})
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
      await page.screenshot({ path: path.join(shots, "e52-" + width + ".png"), fullPage: true });
      await page.close();
    }

    // 2b. TLS revival: matrix, pinned components, diagnostics that say where they ran.
    page = await open("en", 1366);
    await page.locator("#revive-tls").waitFor();
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
    assert((await plan.innerText()).includes("SymPort-TLS/MBedTLS.sis"));
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
    await page.screenshot({ path: path.join(shots, "tls-1366.png"), fullPage: true });
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
    await page.screenshot({ path: path.join(shots, "n95-unknown-rm.png"), fullPage: true });
    await page.close();

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
