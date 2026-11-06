// Editable SVG masters -> alpha PNG / WebP at 1000px; both use independent embedded reference-based layers.
const { chromium } = require("playwright"),
  path = require("path");
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
      viewport: { width: 1000, height: 1868 },
      deviceScaleFactor: 1,
    });
    const models = process.argv.slice(2);
    for (const model of models.length
      ? models
      : [
          "nokia-n95",
          "nokia-n95-8gb",
          "nokia-n8",
          "nokia-e7",
          "nokia-e7-open",
        ]) {
      if (!/^nokia-[a-z0-9-]+$/.test(model))
        throw Error("Invalid artwork name");
      const file = path.resolve(
        __dirname,
        "../../symport/web_assets/phones/" + model,
      );
      const source = require("fs").readFileSync(file + ".svg", "utf8");
      const [, width, height] = /viewBox="0 0 (\d+) (\d+)"/.exec(source) ?? [];
      if (!width || !height) throw Error("Missing artwork geometry");
      await page.setViewportSize({
        width: Number(width),
        height: Number(height),
      });
      await page.setContent(source);
      await page.addStyleTag({
        content: "html,body{margin:0;background:transparent}svg{display:block}",
      });
      await page.screenshot({ path: file + ".png", omitBackground: true });
      const exportResult = require("child_process").spawnSync(
        process.env.SYMPORT_PYTHON || "python3",
        [
          "-c",
          "from PIL import Image; import sys; im=Image.open(sys.argv[1]+'.png'); im.save(sys.argv[1]+'.webp',lossless=True,method=6)",
          file,
        ],
        { stdio: "inherit" },
      );
      if (exportResult.status !== 0) throw Error("WebP export requires Pillow");
    }
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
