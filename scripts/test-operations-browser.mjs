// Real Angular -> Go -> Python -> SQLite document flow, using synthetic input only.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { mkdir, mkdtemp, writeFile, readFile } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import { once } from "node:events";
import { chromium } from "playwright-core";
import axe from "axe-core";
import { isolate } from "./browser-harness.mjs";
const root = process.cwd(),
  output = "artifacts/operations20/ui";
await mkdir(output, { recursive: true });
const storage = await mkdtemp(path.join(root, output, "workspace-"));
const python =
  process.env.VEYA_PYTHON ||
  path.join(
    root,
    "services/runtime/.venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const token = randomBytes(32).toString("hex");
const child = spawn(
  path.join(
    root,
    "apps/desktop/src-tauri/binaries",
    process.platform === "win32" ? "veya-platform.exe" : "veya-platform",
  ),
  [
    "--python",
    python,
    "--runtime",
    path.join(root, "services/runtime"),
    "--assets",
    path.join(root, "apps/desktop/dist"),
  ],
  { stdio: ["pipe", "pipe", "pipe"], windowsHide: true },
);
const exit = once(child, "exit"),
  lines = readline.createInterface({ input: child.stdout });
const ready = new Promise((resolve, reject) => {
  const timer = setTimeout(() => {
    child.kill();
    reject(Error("Platform timeout"));
  }, 16000);
  lines.once("line", (line) => {
    clearTimeout(timer);
    try {
      resolve(JSON.parse(line));
    } catch (e) {
      reject(e);
    }
  });
  child.once("error", (e) => {
    clearTimeout(timer);
    reject(e);
  });
  child.once("exit", () => {
    clearTimeout(timer);
    reject(Error("Platform exited"));
  });
});
child.stdin.write(
  JSON.stringify({ protocol: 1, storage_root: storage, session_token: token }) +
    "\n",
);
const status = await ready;
assert.equal(status.status, "ready");
const origin = `http://127.0.0.1:${status.port}`;
const browser = await chromium.launch({
  executablePath:
    process.env.VEYA_CHROME ||
    (process.platform === "win32"
      ? "C:/Program Files/Google/Chrome/Application/chrome.exe"
      : undefined),
  headless: true,
}).catch((error) => { child.stdin.end(); throw error; });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  reducedMotion: "reduce",
  serviceWorkers: "block",
});
await isolate(context, origin);
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
async function a11y(label) {
  await page.evaluate(axe.source);
  const result = await page.evaluate(() =>
    window.axe.run(document.querySelector(".veya-workspace"), {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
      },
    }),
  );
  assert.deepEqual(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
    [],
    label,
  );
}

async function contract() {
  return page.evaluate(() => {
    const el = document.querySelector('.veya-workspace');
    const style = getComputedStyle(el);
    return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      font: style.fontFamily, size: style.fontSize, text: style.color,
      headings: document.querySelectorAll('h1').length,
      controls: [...document.querySelectorAll('button')].filter(b => b.getBoundingClientRect().width > 0).length };
  });
}
function validate(actual) {
  assert.ok(actual.scrollWidth <= actual.width, 'Core screen overflows viewport');
  assert.match(actual.font, /Public Sans/);
  assert.equal(actual.size, '14px');
  assert.equal(actual.text, 'rgb(41, 45, 41)');
  assert.equal(actual.headings, 1);
  assert.ok(actual.controls >= 5, 'Empty screen cannot pass');
}
let checks = 0;
try {
  await page.goto(origin + '/#session=' + token);
  await page.getByRole('button', {name:'Connected',exact:true}).waitFor();
  for (const width of [1440,800]) {
    await page.setViewportSize({width,height:width === 800 ? 640 : 1000});
    await page.evaluate(() => document.fonts.ready);
    const actual = await contract(); validate(actual); await a11y('Core screen');
    await writeFile(output + '/contract-' + width + '.json', JSON.stringify(actual,null,2));
    await page.screenshot({path:output + '/workspace-' + width + '.png'}); checks++;
  }
  await page.setViewportSize({width:1440,height:1000});
  const expected = await contract();
  const mutation = await page.addStyleTag({content:'.veya-workspace { min-width: 200vw !important; }'});
  const broken = await contract();
  assert.throws(() => validate(broken), /overflows/);
  await page.screenshot({path:output + '/deliberately-broken.png'});
  await writeFile(output+'/regression-diff.json', JSON.stringify({expected,actual:broken,detected:true},null,2));
  await mutation.evaluate(el => el.remove());
  validate(await contract()); checks++;
  await page.getByRole('button',{name:'Connected',exact:true}).click();
  const prepare = page.getByRole('button',{name:'Prepare diagnostic report',exact:true});
  await prepare.waitFor(); await prepare.focus(); await page.keyboard.press('Enter');
  await page.getByRole('button',{name:'Save diagnostic report',exact:true}).waitFor();
  await a11y('Diagnostic ready');
  await page.screenshot({path:output+'/diagnostics-1440.png'});
  const download = page.waitForEvent('download');
  await page.getByRole('button',{name:'Save diagnostic report',exact:true}).click();
  await (await download).saveAs(output+'/diagnostics.json');
  const report = JSON.parse(await readFile(output+'/diagnostics.json','utf8'));
  assert.equal(createHash('sha256').update(report.content).digest('hex'),report.sha256);
  assert.ok(report.records > 0);
  assert.ok(!report.content.includes(token)); checks++;
  await page.setViewportSize({width:800,height:640}); await a11y('Diagnostic compact');
  await prepare.focus(); await page.keyboard.press('Tab');
  await page.getByRole('button',{name:'Save diagnostic report',exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:output+'/diagnostics-800.png'});
  await page.route('**/api/workspace', route => route.request().postDataJSON().operation === 'export_diagnostics' ? route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'busy',message:'Busy'}})}) : route.continue());
  await prepare.click();
  await page.getByRole('alert').filter({hasText:'report could not be prepared'}).waitFor();
  assert.ok(await page.getByRole('button',{name:'Save diagnostic report',exact:true}).isVisible());
  await a11y('Diagnostic retry');
  await page.screenshot({path:output+'/diagnostics-retry.png'});
  await page.unroute('**/api/workspace');
  await prepare.click();
  await page.waitForFunction(() => !document.querySelector('.work-diagnostics [role=alert]'));
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'hidden'}); checks++;
  assert.deepEqual(errors,[]); assert.equal(checks,5);
  await writeFile(output+'/result.json',JSON.stringify({passed:true,checks,stack:['Angular','Go','Python'],widths:[1440,800],mutationDetected:true},null,2));
  console.log('PASS: real diagnostics download, retry, keyboard, accessibility, rendered contract and broken-screen detection');
} catch(error) {
  await page.screenshot({path:output+'/failure.png'}).catch(()=>{});
  await writeFile(output+'/failure.txt',String(error));
  throw error;
} finally {
  await browser.close(); child.stdin.end(); await exit; lines.close();
}
