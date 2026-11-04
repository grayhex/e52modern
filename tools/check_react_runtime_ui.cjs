// Real React -> Python -> pinned MGO/EKA2L1, disposable instance without user ROM.
const { chromium } = require("playwright"),
  fs = require("fs"),
  path = require("path");
const base = process.env.SYMPORT_RUNTIME_URL || "http://127.0.0.1:8775",
  shots = path.resolve(__dirname, "../build/screenshots/react");
fs.mkdirSync(shots, { recursive: true });
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.SYMPORT_BROWSER_EXECUTABLE
      ? { executablePath: process.env.SYMPORT_BROWSER_EXECUTABLE }
      : {}),
    args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(base + "/next/#lab");
    await page.selectOption("#language", "en");
    await page.selectOption("#theme", "dark");
    async function call(body) {
      return page.evaluate(async (body) => {
        const token = document.querySelector(
          "meta[name=symport-token]",
        ).content;
        const response = await fetch("/api/lab", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Symport-Token": token,
          },
          body: JSON.stringify(body),
        });
        const result = await response.json();
        if (!response.ok) throw Error(result.error);
        return result;
      }, body);
    }
    let state;
    for (let i = 0; i < 40; i++) {
      state = await call({ action: "state" });
      if (state.available) break;
      await page.waitForTimeout(500);
    }
    if (!state.available || !state.health.emulator.includes("EKA2L1 master-"))
      throw Error("Real pinned MGO unavailable");
    if (state.health.firmware.devices.length)
      throw Error("Refusing test with user firmware");
    if (
      !(await page
        .getByRole("button", { name: "Start", exact: true })
        .isDisabled())
    )
      throw Error("Start enabled without firmware");
    if ((await page.locator(".nav-link .asset-icon").count()) !== 20)
      throw Error("Navigation graphics missing");
    await page.getByLabel("Format", { exact: true }).selectOption("vpl");
    await page.getByLabel("VPL + FPSX", { exact: true }).setInputFiles([
      {
        name: "synthetic.vpl",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("<not-a-vpl/>"),
      },
      {
        name: "synthetic.fpsx",
        mimeType: "application/octet-stream",
        buffer: Buffer.from("INVALID TEST DATA"),
      },
    ]);
    await page
      .getByRole("button", { name: "Upload files", exact: true })
      .click();
    await page.waitForFunction(() =>
      [...document.querySelectorAll("button")].some(
        (b) => b.textContent === "Install firmware" && !b.disabled,
      ),
    );
    await page
      .getByRole("button", { name: "Install firmware", exact: true })
      .click();
    await page.getByRole("button", { name: "Confirm", exact: true }).click();
    let report;
    for (let i = 0; i < 160; i++) {
      const state = await call({ action: "state" });
      const latest = state.reports[0];
      if (latest && !latest.running) {
        report = await call({ action: "report", id: latest.id });
        break;
      }
      await page.waitForTimeout(500);
    }
    if (
      !report ||
      report.install !== "failed" ||
      report.agent_job?.errorCode !== "vpl_invalid" ||
      report.screenshots.length ||
      report.physical_device !== "not-tested"
    )
      throw Error("Real failure evidence changed: " + JSON.stringify(report));
    await page.getByText("failed", { exact: true }).first().waitFor();
    if (await page.getByRole("alert").count())
      throw Error(
        "Unexpected React contract error: " +
          (await page.getByRole("alert").allTextContents()),
      );
    await page.screenshot({
      path: path.join(shots, "real-mgo-invalid-firmware.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw Error("Mobile overflow");
    if (errors.length) throw Error(errors.join("\n"));
    console.log(
      "PASS real React/MGO/EKA2L1: no-ROM disabled controls, original VPL/FPSX upload, real vpl_invalid failure, durable report, no fabricated screenshot.",
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
