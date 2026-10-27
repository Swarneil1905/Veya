// Real Angular -> Go -> Python -> SQLite document flow, using synthetic input only.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import { once } from "node:events";
import { chromium } from "playwright-core";
import axe from "axe-core";
import { isolate } from "./browser-harness.mjs";
const root = process.cwd(),
  output = "artifacts/research20";
await mkdir(output, { recursive: true });
const storage = await mkdtemp(path.join(root, output, "workspace-"));
const python =
  process.env.VEYA_PYTHON ||
  path.join(
    root,
    "services/runtime/.venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const seed = spawnSync(python, ["scripts/seed_research_fixture.py", storage], {
  encoding: "utf8",
  windowsHide: true,
});
assert.equal(seed.status, 0, seed.stderr);
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
});
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
async function command(name) {
  await page.keyboard.press("Control+k");
  await page.getByLabel("Find a command", { exact: true }).fill(name);
  await page.keyboard.press("Enter");
}

try {
  await page.goto(origin + "/#session=" + token);
  await page.getByRole("button", { name: "Connected", exact: true }).waitFor();
  await command("Engineering evaluations");
  await page
    .getByRole("heading", { name: "Evaluations", exact: true })
    .waitFor();
  await page
    .getByRole("button", { name: /Invoice review - synthetic comparison/ })
    .waitFor();
  await a11y("Evaluation list");
  await page.screenshot({ path: output + "/evaluations-1440.png" });
  await page
    .getByRole("button", { name: /Invoice review - synthetic comparison/ })
    .click();
  await page.getByRole("dialog").waitFor();
  assert.equal(await page.getByRole("table").count(), 1);
  await page
    .getByLabel("Task family", { exact: true })
    .selectOption("quantity");
  assert.equal(
    await page.getByRole("dialog").locator(".research-row").count(),
    2,
  );
  await page
    .getByRole("button", { name: /fixture_quantity candidate/ })
    .click();
  await page
    .getByRole("heading", { name: "quantity_candidate", exact: true })
    .waitFor();
  assert.match(
    await page.getByLabel("Exact run evidence").innerText(),
    /quantity_candidate_audit/,
  );
  await a11y("Exact evaluation evidence");
  await page.screenshot({ path: output + "/evaluation-detail-1440.png" });
  await page.keyboard.press("Escape");
  await command("Review dataset examples");
  await page.getByRole("button", { name: /fixture_case/ }).click();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Inspected the original fixture amount and provenance.");
  await page
    .getByRole("button", { name: "Approve example", exact: true })
    .click();
  await page.getByText("Review saved. Original evidence preserved.").waitFor();
  assert.match(
    await page.getByRole("dialog").innerText(),
    /workspace_owner.*revision 1/,
  );
  await a11y("Reviewed trajectory");
  await page.screenshot({ path: output + "/review-1440.png" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /fixture_restricted/ }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "Approve example", exact: true })
      .isDisabled(),
    true,
  );
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Source permission is absent.");
  await page
    .getByRole("button", { name: "Reject example", exact: true })
    .click();
  await page.getByText("Review saved. Original evidence preserved.").waitFor();
  await page.keyboard.press("Escape");
  await page.reload();
  await page.getByRole("button", { name: "Connected", exact: true }).waitFor();
  await command("Review dataset examples");
  await page.getByRole("button", { name: /fixture_case/ }).click();
  assert.match(
    await page.getByRole("dialog").innerText(),
    /workspace_owner.*revision 1/,
  );
  await page.setViewportSize({ width: 1024, height: 768 });
  await a11y("Review at minimum desktop width");
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({ path: output + "/review-1024.png" });
  await page.keyboard.press("Escape");
  await page.route("**/api/workspace", async (route) => {
    const body = route.request().postDataJSON();
    if (body.operation === "list_trajectories")
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: { code: "busy" } }),
      });
    else await route.continue();
  });
  await page
    .getByRole("button", { name: "Refresh examples", exact: true })
    .click();
  await page.getByRole("alert").filter({ hasText: "busy" }).waitFor();
  await a11y("Research retry state");
  await page.unroute("**/api/workspace");
  await page
    .getByRole("button", { name: "Refresh examples", exact: true })
    .click();
  await page.getByRole("button", { name: /fixture_case/ }).waitFor();
  await page.getByRole('button',{name:/fixture_case/}).click();
  await page.getByLabel('Review note',{exact:true}).fill('Retain this review note through reconnect.');
  let releaseSave;
  const saveGate=new Promise(resolve=>{releaseSave=resolve;});
  await page.route('**/api/workspace',async route=>{
    if(route.request().postDataJSON().operation==='review_trajectory'){await saveGate;await route.abort();}else await route.continue();
  });
  await page.getByRole('button',{name:'Approve example',exact:true}).click();
  await page.route('**/api/health',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'busy'}})}));
  await page.getByRole('button',{name:'Disconnected',exact:true}).waitFor();
  releaseSave();await page.unroute('**/api/workspace');await page.unroute('**/api/health');
  await page.getByRole('button',{name:'Connected',exact:true}).waitFor();
  await page.getByRole('button',{name:/fixture_case/}).click();
  assert.equal(await page.getByLabel('Review note',{exact:true}).inputValue(),'Retain this review note through reconnect.');
  assert.equal(await page.getByRole('button',{name:'Approve example',exact:true}).isEnabled(),true);
  await page.getByRole('button',{name:'Approve example',exact:true}).click();
  await page.getByText('Review saved. Original evidence preserved.').waitFor();
  assert.deepEqual(errors, []);
  await writeFile(
    output + "/browser-result.json",
    JSON.stringify(
      {
        passed: true,
        realStack: ["Angular", "Go", "Python", "SQLite"],
        widths: [1440, 1024],
        checks: [
          "list",
          "paired-metrics",
          "family-filter",
          "exact-evidence",
          "review-approval",
          "permission-denial",
          "rejection",
          "durable-review",
          "keyboard",
          "retry",
          "axe",
        "interrupted-save-reconnect",
        "review-note-retained",
        ],
        syntheticOnly: true,
      },
      null,
      2,
    ),
  );
  console.log(
    "PASS research browser: real stack, reviews, evidence, keyboard, retry, accessibility",
  );
} finally {
  await browser.close();
  child.stdin.end();
  await exit;
  lines.close();
}
