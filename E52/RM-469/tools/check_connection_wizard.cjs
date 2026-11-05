const { chromium } = require("playwright"),
  { spawn } = require("child_process"),
  fs = require("fs"),
  os = require("os"),
  path = require("path");
const repo = path.resolve(__dirname, ".."),
  root = fs.mkdtempSync(path.join(os.tmpdir(), "symport-wizard-")),
  python = process.env.SYMPORT_PYTHON || "python3",
  shots = path.join(repo, "build/screenshots/react");
fs.mkdirSync(shots, { recursive: true });
for (const name of ["theme", "tools", "profiles", "catalog"])
  fs.cpSync(path.join(repo, name), path.join(root, name), { recursive: true });
const symport = `import sys,os,json
from pathlib import Path
from symport.web import main
r=Path(sys.argv[1]);os.environ.update(SYMPORT_DEVICE_ROOTS='{}',SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_BRIDGE_URL='')
main(['--repo',str(r),'--port','8787'])`;
// The real BridgeServer and OutboundRelay with a synthetic phone behind a stub transport (not a phone).
const bridge = `import sys,threading,time
from pathlib import Path
from symport.bridge.server import BridgeServer
from symport.bridge.relay import OutboundRelay
from symport.phone import DeviceManager, capabilities
mode=sys.argv[1]
class Transport:
    def devices(self):
        if mode!='approve': return []
        return [capabilities.apply(dict(id='usb',name='Nokia E52',transport='gammu',connection_kind='gammu-usb',connected=True,model='Nokia E52 (RM-469)',rm='RM-469',firmware='071.004',evidence='Synthetic test transport'), capabilities.Matrix().available('identity.read','test-double','synthetic').available('contacts.read','test-double','synthetic').untested('files.upload','test-double','synthetic'))]
    def execute(self,data):
        if data['action']=='connection-host':
            return dict(serial=[dict(port='COM3',vendor='Nokia')],bluetooth=[],volumes=[],usb=[dict(vid='0421',pid='01a2',class_='Ports',status='ok')],diagnostics=[],environment=dict(bridge_version='0.2.0',os='Windows 10',python_gammu=True))
        raise ValueError('unsupported in test')
    def diagnostics(self): return []
manager=DeviceManager(Path(sys.argv[2]),Transport())
class Agent:
    stop=threading.Event()
agent=Agent();agent.manager=manager
server=BridgeServer(manager,'k'*32,24652,[],lambda data:True)
agent.server=server
relays=[]
def pair(origin,token):
    if mode=='declined': return False
    relay=OutboundRelay(agent,origin,token);relays.append(relay);relay.thread.start();return True
server.pair=pair
server.serve_forever()`;
const spawned = [];
const run = (code, ...args) => {
  const child = spawn(python, ["-c", code, ...args], { cwd: repo, env: process.env, stdio: ["ignore", "ignore", "inherit"] });
  spawned.push(child);
  return child;
};
const stop = (child) => new Promise((r) => { child.once("exit", r); child.kill(); });
let currentPage;
(async () => {
  let browser;
  try {
    run(symport, root);
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE } : {}),
      args: ["--no-sandbox"],
    });
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
    const page = await context.newPage(),
      errors = [];
    currentPage = page;
    page.setDefaultTimeout(20000);
    page.on("pageerror", (error) => errors.push(error.message));
    for (let i = 0; i < 50; i++) {
      try { await page.goto("http://127.0.0.1:8787/next/#phone/connection"); break; }
      catch { await new Promise((r) => setTimeout(r, 200)); }
    }
    await page.getByRole("button", { name: "Настройки", exact: true }).click();
    await page.selectOption("#language", "en");
    const wizard = page.locator(".wizard");
    const step = (id, status) => wizard.locator(`[data-step="${id}"][data-status="${status}"]`);
    // Local transports: Bridge and pairing are not needed, and no phone is invented.
    await step("bridge", "skipped").waitFor();
    await step("identify", "pending").waitFor();
    // Switch to the Bridge path by requesting access while no Bridge runs.
    await wizard.getByRole("button", { name: "Request access" }).click();
    await step("pairing", "failed").waitFor();
    if (!(await step("pairing", "failed").innerText()).includes("pair-unreachable"))
      throw Error("Unreachable Bridge during pairing was not classified");
    await step("bridge", "skipped").waitFor(); // the lease was released, local transports are back
    // Declined on the PC.
    const declined = run(bridge, "declined", root);
    await new Promise((r) => setTimeout(r, 1500));
    await wizard.getByRole("button", { name: "Check Bridge" }).click();
    await step("bridge", "success").waitFor(); // reachable: the probe never opens an approval dialog
    await wizard.getByRole("button", { name: "Request access" }).click();
    await wizard.locator('[data-step="pairing"][data-status="failed"]', { hasText: "pair-declined" }).waitFor();
    await stop(declined);
    // Approved: real probe, real pairing, real outbound relay.
    const approved = run(bridge, "approve", root);
    await new Promise((r) => setTimeout(r, 1500));
    await wizard.getByRole("button", { name: "Request access" }).click();
    await step("pairing", "success").waitFor({ timeout: 40000 });
    await step("usb", "success").waitFor({ timeout: 40000 });
    await step("driver", "success").waitFor();
    await step("identify", "success").waitFor({ timeout: 40000 });
    await step("capabilities", "success").waitFor({ timeout: 40000 });
    if (!(await step("identify", "success").innerText()).includes("RM-469"))
      throw Error("Identity is missing from the wizard");
    const levels = await wizard.locator(".wizard-levels li").evaluateAll((items) => items.map((li) => li.dataset.on));
    if (levels.join() !== "true,true,true,true,false")
      throw Error("Five levels must stay apart: " + levels.join());
    await page.screenshot({ path: path.join(shots, "connection-wizard-light-en.png"), fullPage: true });
    // De-identified report: nothing private, whatever the phone said.
    const href = await wizard.locator('a[download="symport-first-connection-report.json"]').getAttribute("href");
    const report = Buffer.from(href.split(",")[1], "base64").toString("utf8");
    for (const secret of ["COM3", "127.0.0.1", "k".repeat(8), "synthetic"])
      if (report.includes(secret)) throw Error("Report leaks " + secret);
    const parsed = JSON.parse(report);
    if (parsed.hardware_verified !== false || parsed.stage !== "complete")
      throw Error("Unexpected report: " + report.slice(0, 300));
    // Bridge disappears: the lost connection is reported, nothing is retried automatically.
    await stop(approved);
    await wizard.getByRole("button", { name: /Re-run diagnostics/ }).click();
    await page.waitForFunction(() => {
      const el = document.querySelector('.wizard [data-step="pairing"]');
      return el && el.getAttribute("data-status") !== "success";
    }, null, { timeout: 60000 });
    // RU, light, mobile.
    if (!(await page.locator("#language").count()))
      await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.selectOption("#language", "ru");
    await wizard.getByRole("heading", { name: "Мастер первого подключения" }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
      throw Error("Mobile overflow");
    await page.screenshot({ path: path.join(shots, "connection-wizard-light-ru-mobile.png"), fullPage: true });
    if (errors.length) throw Error(errors.join("\n"));
    console.log("PASS connection wizard: real BridgeServer probe/pairing/declined/relay, steps and five levels, lost Bridge, de-identified report, RU/EN, light theme, mobile. Synthetic phone; not a physical E52.");
  } catch (error) {
    try { console.error((await currentPage.locator('.wizard').innerText()).slice(0, 2500)); } catch {}
    throw error;
  } finally {
    await browser?.close();
    for (const child of spawned) child.kill();
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch(async (error) => {
  console.error(error);
  process.exitCode = 1;
});
