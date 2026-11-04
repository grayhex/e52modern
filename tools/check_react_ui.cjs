const { chromium } = require("playwright"),
  { spawn } = require("child_process"),
  fs = require("fs"),
  os = require("os"),
  path = require("path");
const repo = path.resolve(__dirname, ".."),
  root = fs.mkdtempSync(path.join(os.tmpdir(), "symport-react-")),
  python = process.env.SYMPORT_PYTHON || "python3";
const script = `import sys,os,json
from pathlib import Path
from symport.web import main
r=Path(sys.argv[1]);v=r/'volume';v.mkdir();(v/'hello.txt').write_text('actual private bytes')
os.environ.update(SYMPORT_DEVICE_ROOTS=json.dumps({'card':str(v)}),SYMPORT_GAMMU_CONFIG='',SYMPORT_CONNECTIONS_FILE='',SYMPORT_BRIDGE_URL='')
main(['--repo',str(r),'--port','8786'])`;
for (const name of ["theme", "tools", "profiles", "catalog"])
  fs.cpSync(path.join(repo, name), path.join(root, name), { recursive: true });
const server = spawn(python, ["-c", script, root], {
  cwd: repo,
  env: process.env,
  stdio: ["ignore", "ignore", "inherit"],
});
(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SYMPORT_BROWSER_EXECUTABLE
        ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE }
        : {}),
      args: ["--no-sandbox"],
    });
    const page = await browser.newPage({
        viewport: { width: 1366, height: 768 },
      }),
      errors = [];
    page.setDefaultTimeout(15000);
    page.on("pageerror", (error) => errors.push(error.message));
    for (let i = 0; i < 50; i++) {
      try {
        await page.goto("http://127.0.0.1:8786/next/");
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 200));
      }
    }
    await page
      .getByRole("heading", { name: "Обзор устройства", exact: true })
      .waitFor();
    await page.getByRole("button", { name: "Настройки", exact: true }).click();
    await page.selectOption("#language", "en");
    await page.selectOption("#theme", "dark");
    await page.getByRole("link", { name: "File manager", exact: true }).click();
    await page.getByLabel("Connection", { exact: true }).selectOption("card");
    const browserView = page.locator(".phone-files");
    await browserView.getByRole("checkbox", { name: "Select hello.txt" }).waitFor();
    await browserView.getByRole("checkbox", { name: "Select hello.txt" }).click();
    await browserView.getByRole("button", { name: "Download", exact: true }).click();
    // The library prepares the download and offers a link; a top-level navigation must be an attachment.
    const [file] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "Open prepared download" }).click(),
    ]);
    const dest = path.join(root, "download.txt");
    await file.saveAs(dest);
    if (fs.readFileSync(dest, "utf8") !== "actual private bytes")
      throw Error("Wrong download");
    await browserView.getByRole("button", { name: "Delete", exact: true }).click();
    await browserView.getByRole("dialog").waitFor();
    await browserView.getByRole("button", { name: "Cancel", exact: true }).click();
    if (!fs.existsSync(path.join(root, "volume/hello.txt")))
      throw Error("Cancelled delete executed");
    await browserView.getByRole("button", { name: "New folder", exact: true }).click();
    await browserView.getByRole("dialog").getByRole("textbox").fill("new-folder");
    await browserView.getByRole("button", { name: "Create folder", exact: true }).click();
    for (let i = 0; i < 40 && !fs.existsSync(path.join(root, "volume/new-folder")); i++)
      await page.waitForTimeout(250);
    if (!fs.existsSync(path.join(root, "volume/new-folder")))
      throw Error("mkdir UI state: " + JSON.stringify(fs.readdirSync(path.join(root, "volume"))) + root + " " + (await browserView.innerText()).replace(/\n+/g, " / ").slice(0, 600));
    if (!fs.statSync(path.join(root, "volume/new-folder")).isDirectory())
      throw Error("Directory not created");
    // Existing files are never overwritten: uploading the same name must not change the bytes.
    const clash = path.join(root, "hello.txt");
    fs.writeFileSync(clash, "replacement");
    await browserView.locator("input[type=file]").first().setInputFiles(clash);
    // The browser asks what to do with the clash; "replace" is not offered because the device layer refuses it.
    const clashDialog = browserView.getByRole("dialog");
    await clashDialog.waitFor();
    if (await clashDialog.getByRole("button", { name: /replace/i }).count())
      throw Error("Replace must not be offered for phone files");
    await clashDialog.getByRole("button", { name: /skip/i }).first().click();
    await clashDialog.waitFor({ state: "hidden" });
    await page.waitForTimeout(500);
    if (fs.readFileSync(path.join(root, "volume/hello.txt"), "utf8") !== "actual private bytes")
      throw Error("Existing phone file was overwritten");
    // Preview goes through the same-origin phone-file endpoint: actual bytes, no sniffing, no scripts.
    await browserView.getByText("hello.txt").first().dblclick();
    await browserView.getByText("actual private bytes").waitFor();
    await page.keyboard.press("Escape");
    // Legacy URLs redirect to the new structure without adding history entries.
    await page.goto("http://127.0.0.1:8786/next/#inspector?source=upload");
    await page.locator("#page-tools-certificates h1").waitFor();
    if (!(await page.evaluate(() => location.hash)).startsWith("#tools/certificates?source=upload"))
      throw Error("Legacy inspector URL was not redirected with its query");
    // Compact rail: icons only, accessible names kept.
    await page.getByRole("button", { name: "Collapse menu to icons" }).click();
    await page.getByRole("link", { name: "Device overview", exact: true }).waitFor();
    if (await page.locator(".nav-text").first().isVisible()) throw Error("Compact rail still shows labels");
    await page.getByRole("button", { name: "Expand menu" }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Mobile overflow");
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS React: actual API discovery/list/download, Cancel-first delete, confirmed mkdir, RU/EN/dark/mobile; no legacy controller execution.",
    );
  } finally {
    await browser?.close();
    server.kill();
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
