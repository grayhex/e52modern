// React parity: actual Python API/files/FFmpeg; explicit stateful phone + MGO contract doubles.
// These fixtures are never exposed by the production discovery path.
const { chromium } = require("playwright"),
  { spawn, spawnSync } = require("child_process"),
  fs = require("fs"),
  os = require("os"),
  path = require("path");
const repo = path.resolve(__dirname, ".."),
  root = fs.mkdtempSync(path.join(os.tmpdir(), "symport-react-parity-")),
  python = process.env.SYMPORT_PYTHON || "python3",
  shots = path.join(repo, "build/screenshots/react");
fs.mkdirSync(shots, { recursive: true });
for (const name of ["theme", "tools", "profiles", "catalog"])
  fs.cpSync(path.join(repo, name), path.join(root, name), { recursive: true });
const script = `import sys,os,json
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
from tests.test_device_workspace import MockPhone
from tests.test_ringtone import audio_bytes
from tests.test_security_workspace import archive_bytes
from tests.lab_fixture import MockMgo,sis
from symport.web import Workbench,make_handler
from symport.phone.local import LocalTransports
r=Path(sys.argv[1]);v=r/'volume';(v/'Images').mkdir(parents=True);Image.new('RGB',(640,480),'#22d3ee').save(v/'Images/sample.jpg');(v/'sample.wav').write_bytes(audio_bytes(8));(v/'hello.txt').write_text('Keep this original');(r/'fixture.zip').write_bytes(archive_bytes());(r/'app.sis').write_bytes(sis());(r/'theme.sis').write_bytes(sis(True))
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'card':str(v)}),SYMPORT_GAMMU_CONFIG='mock-only',SYMPORT_CONNECTIONS_FILE='',SYMPORT_MGO_URL='',SYMPORT_BRIDGE_URL='')
w=Workbench(r);local=LocalTransports(r);phone=MockPhone();local.personal.invoke=phone.invoke
from tests.capfake import row as capability_row
local.devices=lambda:local.files.devices()+[capability_row(dict(phone.identity,id='gammu',transport='gammu',connected=True,model='Nokia E52 (mock transport)',firmware='081.003',sms_send_verified=False),available=['identity.read','contacts.read','calendar.read','tasks.read','sms.read'])]
w.devices.transport=local;w.lab.agent=MockMgo()
ThreadingHTTPServer(('127.0.0.1',8787),make_handler(w)).serve_forever()`;
const server = spawn(python, ["-c", script, root], {
  cwd: repo,
  env: process.env,
  stdio: ["ignore", "ignore", "inherit"],
});
(async () => {
  let browser, page;
  try {
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE
        ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE }
        : {}),
      args: ["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
    });
    page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
      timezoneId: "Europe/Moscow",
    });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    for (let i = 0; i < 50; i++) {
      try {
        await page.goto("http://127.0.0.1:8787/");
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
    await page.locator("#page-phone-overview h1").waitFor();
    await page.getByRole("button", { name: "Настройки", exact: true }).click();
    await page.selectOption("#language", "en");
    await page.selectOption("#theme", "dark");
    // Legacy URLs must keep working: navigation below deliberately uses the pre-restructure hash ids.
    const canonical = {
      manager: "phone/overview",
      files: "phone/files",
      connection: "phone/connection",
      contacts: "phone/contacts",
      messages: "phone/messages",
      calendar: "phone/calendar",
      media: "phone/media",
      backups: "phone/backups",
      catalog: "apps/catalog",
      installed: "apps/installed",
      themes: "personalize/themes",
      ringtone: "personalize/ringtones",
      updates: "tools/diagnostics",
      inspector: "tools/certificates",
      jailbreak: "tools/jailbreak",
      activity: "tools/activity",
      device: "tools/diagnostics",
      lab: "dev/lab",
      apps: "dev/sdk",
      overview: "dev/sdk",
    };
    async function go(id) {
      await page.evaluate((id) => {
        location.hash = id;
      }, id);
      const route = canonical[id.split("?")[0]] ?? id.split("?")[0];
      await page.locator("#page-" + route.replace("/", "-") + " h1").first().waitFor();
      const hash = await page.evaluate(() => location.hash);
      if (!hash.startsWith("#" + route)) throw Error("Redirect failed: " + id + " -> " + hash);
    }
    async function button(name) {
      await page.getByRole("button", { name, exact: true }).click();
    }
    async function confirm() {
      await page.getByRole("dialog").waitFor();
      await button("Confirm");
      await page.getByRole("dialog").waitFor({ state: "hidden" });
    }
    async function saved(action, name) {
      const event = page.waitForEvent("download");
      await action();
      const download = await event;
      const dest = path.join(root, name);
      await download.saveAs(dest);
      return fs.readFileSync(dest);
    }
    async function noErrors() {
      const alerts = await page.getByRole("alert").allTextContents();
      if (alerts.length) throw Error("UI error: " + alerts.join("\n"));
    }
    await go("contacts");
    await page
      .locator(".react-page:visible")
      .getByLabel("Connection", { exact: true })
      .selectOption("gammu");
    await button("Read phone");
    await page.locator('input[aria-label="phones: Private Contact"]').waitFor();
    await page
      .locator('input[aria-label="phones: Private Contact"]')
      .fill("+987654321");
    await button("Preview synchronization");
    await page
      .getByRole("heading", { name: "Synchronization preview" })
      .waitFor();
    await page.getByText("Before → after", { exact: true }).click();
    if (
      !(await page.locator("#page-phone-contacts pre").innerText()).includes("+987654321")
    )
      throw Error("Contact preview omitted edited field");
    await button("Apply changes");
    const backup = await saved(confirm, "contacts-backup.json");
    if (!backup.includes("+123456789"))
      throw Error("Original contact not backed up");
    await page
      .getByRole("status")
      .filter({ hasText: "Verified by read-back" })
      .waitFor();
    await noErrors();
    await page
      .locator(".react-page:visible")
      .getByLabel("Contact file")
      .setInputFiles({
        name: "google.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(
          "Name,Given Name,Phone 1 - Value,E-mail 1 - Value\nCloud Person,Cloud,+12345678,cloud@example.test\n",
        ),
      });
    await button("Preview file");
    await page.locator('input[aria-label="name: Cloud Person"]').waitFor();
    const vcard = await saved(() => button("Export vCard"), "cloud.vcf");
    if (!vcard.includes("Cloud Person"))
      throw Error("Cloud import/export failed");
    await go("messages");
    await button("Read phone");
    await page.getByText("=PRIVATE-SMS", { exact: true }).waitFor();
    await page
      .locator(".react-page:visible")
      .getByLabel("Search", { exact: true })
      .fill("absent");
    if (await page.locator(".pim-thread").count())
      throw Error("SMS filter failed");
    await page
      .locator(".react-page:visible")
      .getByLabel("Search", { exact: true })
      .fill("");
    const csv = await saved(() => button("Export CSV"), "sms.csv");
    if (!csv.includes("'=PRIVATE-SMS"))
      throw Error("SMS CSV formula protection missing");
    if (
      !(await page
        .getByRole("button", { name: "Send SMS", exact: true })
        .isDisabled())
    )
      throw Error("Unverified SMS enabled");
    await noErrors();
    await go("calendar");
    await button("Read phone");
    await page
      .getByRole("cell", { name: "Private appointment", exact: true })
      .waitFor();
    await button("Edit");
    await page
      .locator(".react-page:visible")
      .getByLabel("Title", { exact: true })
      .fill("Edited through React");
    await button("Preview changes");
    await button("Apply changes");
    await saved(confirm, "calendar-backup.json");
    await page
      .getByRole("status")
      .filter({ hasText: "Verified by read-back" })
      .waitFor();
    await page
      .locator(".react-page:visible")
      .getByLabel("Store", { exact: true })
      .selectOption("tasks");
    await button("Read phone");
    await page
      .getByRole("cell", { name: "Private task", exact: true })
      .waitFor();
    await button("New entry");
    await page
      .locator(".react-page:visible")
      .getByLabel("Title", { exact: true })
      .fill("Task from React");
    await page
      .locator(".react-page:visible")
      .getByLabel("Due", { exact: true })
      .fill("2030-01-03T12:00");
    await button("Preview changes");
    await page
      .getByRole("heading", { name: "Synchronization preview" })
      .waitFor();
    await noErrors();
    await go("media");
    await page.locator("#page-phone-media > .card select").first().selectOption("card");
    await button("Read gallery");
    await page.locator(".media-item").first().waitFor();
    await page.locator(".media-item img").waitFor();
    await page
      .locator(".react-page:visible")
      .getByLabel("Media type")
      .selectOption("audio");
    await page.locator(".media-open").click();
    const range = await page.locator("dialog audio").evaluate(async (n) => {
      const r = await fetch(n.src, { headers: { Range: "bytes=0-43" } });
      return {
        status: r.status,
        raw: [...new Uint8Array(await r.arrayBuffer())],
      };
    });
    if (
      range.status !== 206 ||
      String.fromCharCode(...range.raw.slice(0, 4)) !== "RIFF"
    )
      throw Error("Ranged audio failed");
    await button("Close");
    await button("Select visible");
    await button("Prepare ZIP (1)");
    await page.getByRole("link", { name: "Download ZIP" }).waitFor();
    const zip = await saved(
      () => page.getByRole("link", { name: "Download ZIP" }).click(),
      "media.zip",
    );
    if (zip.slice(0, 2).toString() !== "PK") throw Error("Media ZIP invalid");
    await page.getByRole("link", { name: "Create ringtone" }).click();
    await page.locator("#page-personalize-ringtones h1").waitFor();
    await button("Open gallery file");
    await page.getByRole("button", { name: "Play fragment" }).waitFor();
    await page
      .locator(".react-page:visible")
      .getByLabel("Preset")
      .selectOption("notification");
    await page.locator(".react-page:visible").getByLabel("Start, s").fill("1");
    await page.locator(".react-page:visible").getByLabel("End, s").fill("5");
    await page.getByText("Audio settings", { exact: true }).click();
    await page
      .locator(".react-page:visible")
      .getByLabel("Sample rate, Hz")
      .selectOption("22050");
    await button("Create MP3");
    await page.getByRole("heading", { name: "Processed MP3" }).waitFor();
    const mp3 = await saved(
      () => page.getByRole("link", { name: "Download MP3" }).click(),
      "ringtone.mp3",
    );
    const probe = JSON.parse(
      spawnSync(
        "ffprobe",
        [
          "-v",
          "error",
          "-show_entries",
          "format=duration:stream=channels,sample_rate",
          "-of",
          "json",
          path.join(root, "ringtone.mp3"),
        ],
        { encoding: "utf8" },
      ).stdout,
    );
    if (
      probe.streams[0].channels !== 1 ||
      Math.abs(Number(probe.format.duration) - 4) > 0.15
    )
      throw Error("Processed MP3 invalid");
    await button("Send to Nokia");
    await confirm();
    await page.getByRole("status").filter({ hasText: "completed" }).waitFor();
    const ringtone = fs
      .readdirSync(path.join(root, "volume"))
      .find((n) => n.endsWith(".mp3"));
    if (
      !ringtone ||
      !fs.readFileSync(path.join(root, "volume", ringtone)).equals(mp3)
    )
      throw Error("Transferred MP3 differs");
    await page.getByText("Audio settings", { exact: true }).click();
    await page.setViewportSize({ width: 1366, height: 768 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: path.join(shots, "ringtone-dark-en.png"),
      fullPage: true,
    });
    await go("connection");
    await go("ringtone");
    await page.getByRole("heading", { name: "Processed MP3" }).waitFor();
    if (
      (await page
        .locator(".react-page:visible")
        .getByLabel("End, s")
        .inputValue()) !== "5"
    )
      throw Error("Editor draft lost on navigation");
    await button("Clear");
    await page.setViewportSize({ width: 1440, height: 1000 });
    await noErrors();
    await go("inspector");
    await page
      .locator(".react-page:visible")
      .getByLabel("Package (up to 32 MiB)")
      .setInputFiles(
        path.join(repo, "tests/fixtures/sdk_probe_package_signed.sis"),
      );
    await button("Analyze package");
    await page
      .getByRole("heading", {
        name: "sdk_probe_package_signed.sis",
        exact: true,
      })
      .waitFor();
    await page
      .locator(".react-page:visible")
      .getByLabel("Exact message from phone")
      .fill("expired certificate");
    await button("Explain error");
    await page
      .getByText("expired-certificate", { exact: true })
      .first()
      .waitFor();
    await page.screenshot({
      path: path.join(shots, "inspector-dark-en.png"),
      fullPage: true,
    });
    await noErrors();
    await go("lab");
    await page
      .locator(".react-page:visible")
      .getByLabel("Package (up to 32 MiB)")
      .setInputFiles(path.join(root, "theme.sis"));
    await page
      .locator(".react-page:visible")
      .getByLabel("Package type")
      .selectOption("theme");
    await button("Test in emulator");
    await confirm();
    await page
      .getByRole("heading", { name: "theme.sis", exact: true })
      .waitFor();
    await page
      .getByText(
        "Open Menu → Settings → Themes → General and apply the theme. Record each screen below; theme UID is never launched.",
        { exact: true },
      )
      .waitFor();
    await page
      .getByRole("button", { name: "Record & capture" })
      .waitFor({ state: "visible" });
    await button("Record & capture");
    await page.locator(".lab-gallery img").first().waitFor();
    await page.locator(".lab-handset").focus();
    await page.keyboard.press("ArrowUp");
    await page
      .locator(".react-page:visible")
      .getByLabel("Destination path")
      .fill("tested-theme.sis");
    await button("Transfer");
    await confirm();
    if (
      !fs
        .readFileSync(path.join(root, "volume/tested-theme.sis"))
        .equals(fs.readFileSync(path.join(root, "theme.sis")))
    )
      throw Error("Lab transfer changed bytes");
    await noErrors();
    await go("jailbreak");
    await page
      .locator(".react-page:visible")
      .getByLabel("ZIP · 16 MiB")
      .setInputFiles(path.join(root, "fixture.zip"));
    await button("Inspect archive");
    await page.locator(".lab-upload-entry input").first().waitFor();
    if ((await page.locator(".lab-upload-entry input:disabled").count()) !== 2)
      throw Error("Excluded key/wrong model selectable");
    await page
      .locator(".lab-upload-entry input:not(:disabled)")
      .first()
      .check();
    await page
      .locator(".react-page:visible")
      .getByLabel("Connection", { exact: true })
      .selectOption("card");
    await page
      .locator(".react-page:visible")
      .getByLabel("model", { exact: true })
      .fill("Nokia E52");
    await page
      .locator(".react-page:visible")
      .getByLabel("firmware", { exact: true })
      .fill("unknown");
    await button("Create dry-run plan");
    await page
      .getByRole("heading", { name: "3 / Controlled workflow" })
      .waitFor();
    await button("Back up accessible data");
    await confirm();
    await button("Transfer to isolated folder");
    await confirm();
    await button("Preview rollback");
    await page.getByRole("button", { name: "Remove staged files" }).waitFor();
    await page.waitForFunction(
      () => !document.querySelector("button.btn.destructive").disabled,
    );
    await button("Remove staged files");
    await confirm();
    if (!fs.existsSync(path.join(root, "volume/hello.txt")))
      throw Error("Rollback removed original");
    await noErrors();
    await go("catalog");
    await page.locator(".catalog-app").first().waitFor();
    if ((await page.locator(".catalog-app").count()) < 30)
      throw Error("Catalog entries missing");
    await page
      .locator(".react-page:visible")
      .getByLabel("Search", { exact: true })
      .fill("hotpants");
    if ((await page.locator(".catalog-app").count()) !== 1)
      throw Error("Catalog search failed");
    await button("Details");
    await page.getByRole("dialog").waitFor();
    await button("Close");
    await noErrors();
    await go("themes");
    await page
      .locator(".react-page:visible")
      .getByLabel("SIS / SISX", { exact: true })
      .setInputFiles(path.join(root, "theme.sis"));
    await button("Upload & validate");
    await button("Publish locally");
    await confirm();
    await page.getByRole("link", { name: "Download theme.sis ↓" }).count();
    await noErrors();
    // Every route: no classic script execution, theme/localization persistence, independent scrolling rail and mobile overflow.
    for (const id of [
      "manager",
      "files",
      "connection",
      "ringtone",
      "contacts",
      "calendar",
      "messages",
      "media",
      "backups",
      "catalog",
      "installed",
      "updates",
      "inspector",
      "jailbreak",
      "themes",
      "lab",
      "apps",
      "device",
      "overview",
      "activity",
    ]) {
      await go(id);
      await noErrors();
      await page.setViewportSize({ width: 390, height: 844 });
      const overflow = await page.evaluate(() => {
        if (document.documentElement.scrollWidth <= innerWidth) return null;
        return [...document.querySelectorAll("body *")]
          .filter((el) => el.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(el).display !== "none" && !el.closest("[inert],[hidden]"))
          .slice(0, 6)
          .map((el) => { const b = el.getBoundingClientRect(), c = getComputedStyle(el); return el.tagName + "." + String(el.className) + " left=" + Math.round(b.left) + " right=" + Math.round(b.right) + " width=" + c.width + " margin=" + c.margin + " padding=" + c.padding + " parent=" + Math.round(el.parentElement.getBoundingClientRect().width) + " sw=" + el.scrollWidth + " mainW=" + Math.round(document.querySelector(".main").getBoundingClientRect().width) + " WIDE=" + [...el.querySelectorAll("*")].filter((x) => x.scrollWidth > x.clientWidth + 1 && x.clientWidth > 0).slice(0, 5).map((x) => x.outerHTML.slice(0, 140) + " in " + (x.parentElement.className || x.parentElement.tagName) + ":" + x.scrollWidth + ">" + x.clientWidth).join("|"); });
      });
      if (overflow) throw Error("Mobile overflow: " + id + " " + JSON.stringify(overflow));
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    await go("connection");
    await page
      .locator(".react-page:visible")
      .getByLabel("Connection", { exact: true })
      .selectOption("gammu");
    await button("Reveal IMEI");
    await confirm();
    await page
      .locator("#page-phone-connection code")
      .filter({ hasText: "000000000000000" })
      .waitFor();
    await go("updates");
    await go("connection");
    if (await page.locator("#page-phone-connection code").count())
      throw Error("Private IMEI retained across hidden view");
    await page.selectOption("#language", "ru");
    await page.selectOption("#theme", "light");
    await page.reload();
    await page.waitForFunction(
      () =>
        document.documentElement.lang === "ru" &&
        document.documentElement.dataset.theme === "light",
    );
    if (
      await page
        .locator('script[src$="/app.js"],script[src$="/manager.js"]')
        .count()
    )
      throw Error("Classic controllers loaded");
    const journal = fs.readFileSync(
      path.join(root, "build/symport/device-manager/operations.jsonl"),
      "utf8",
    );
    if (
      /000000000000000|PRIVATE-SMS|123456789|987654321|Private appointment|private@example|Edited through/.test(
        journal,
      )
    )
      throw Error("Private content leaked into journal");
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS React parity: contacts cloud import/sync/backup/readback, SMS CSV/privacy, calendar/tasks, real media thumbnails/Range/ZIP, WaveSurfer/FFmpeg/exact MP3 transfer, signatures, mock MGO themes/keys/screenshots/transfer, controlled staging/rollback, catalog/library, all 20 routes/RU/EN/themes/mobile. Phone and MGO are explicit contract doubles.",
    );
  } catch (error) {
    if (page) {
      console.error((await page.locator("main").innerText()).slice(-8000));
      await page.screenshot({
        path: path.join(shots, "failure.png"),
        fullPage: true,
      });
    }
    throw error;
  } finally {
    await browser?.close();
    server.kill();
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
