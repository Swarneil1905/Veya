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
  output = "artifacts/memory-batch";
await mkdir(output, { recursive: true });
const storage = await mkdtemp(path.join(root, output, "workspace-"));
const python =
  process.env.VEYA_PYTHON ||
  path.join(
    root,
    "services/runtime/.venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const seed = spawnSync(python, ["scripts/seed_memory_fixture.py", storage], {
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
  await page
    .getByRole("button", {
      name: "Open task: Fixture budget failure",
      exact: true,
    })
    .waitFor();
  await page.getByRole("button", { name: "Data review", exact: true }).click();
  await page.getByRole("button", { name: "Lessons", exact: true }).click();
  const lessons = page.getByRole("region", { name: "Reviewed lessons" });
  await lessons
    .getByRole("heading", { name: "Task exceeded its budget", exact: true })
    .waitFor();
  const draft = lessons.getByRole("article", {
    name: "Lesson: Task exceeded its budget",
  });
  const text =
    "For similar invoice tasks, reduce the attached source set before retrying.";
  await draft.getByLabel("Lesson").fill(text);
  await draft
    .getByRole("button", { name: "Approve lesson", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await lessons
    .getByText("Lesson approved for future tasks.", { exact: true })
    .waitFor();
  assert.equal(await draft.getByLabel("Lesson").inputValue(), text);
  const sourceDetails = draft.getByText("Source details", {exact:true});
  await sourceDetails.focus();
  await page.keyboard.press("Enter");
  assert.equal(await draft.locator("details").getAttribute("open"), "");
  assert.match(await draft.locator("details code").innerText(), /^run_/);
  await page.keyboard.press("Enter");
  await a11y("memory review desktop");
  await page.screenshot({
    path: path.join(output, "memory-review-desktop.png"),
    fullPage: true,
  });
  // A stale tab must preserve its draft when the server revision changes.
  await page.evaluate(async () => {
    const send = async (operation, args = {}) => {
      const r = await fetch("/api/workspace", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operation, args }),
      });
      return r.json();
    };
    const result = await send("list_memories");
    const value = result.items ?? result.value?.items;
    if (!value) throw Error("Unexpected memory response");
    const row = value.find((x) => x.topic === "budget_exceeded");
    await send("review_memory", {
      id: row.id,
      revision: row.revision,
      content: row.content,
      action: "activate",
    });
  });
  await draft
    .getByLabel("Lesson")
    .fill("For this task, inspect the supporting receipt before retrying.");
  await draft
    .getByRole("button", { name: "Approve changes", exact: true })
    .click();
  await lessons.getByRole("alert").waitFor();
  assert.match(
    await draft.getByLabel("Lesson").inputValue(),
    /supporting receipt/,
  );
  await lessons
    .getByRole("button", { name: "Refresh lessons", exact: true })
    .click();
  await draft
    .getByRole("button", { name: "Approve changes", exact: true })
    .waitFor({ state: "visible" });
  await page.setViewportSize({ width: 375, height: 800 });
  await a11y("memory review narrow");
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  await page.screenshot({
    path: path.join(output, "memory-review-narrow.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const active = lessons.getByRole("article", { name: "Lesson: Missing supporting evidence" });
  await active.getByRole("button", { name: "Retract", exact: true }).click();
  await lessons
    .getByText("Lesson retracted. It will not inform future tasks.", {
      exact: true,
    })
    .waitFor();
  await active.getByRole("button", { name: "Erase…", exact: true }).click();
  await active
    .getByRole("button", { name: "Confirm erase lesson", exact: true })
    .click();
  await lessons
    .getByText(
      "Lesson text erased. Source task and audit identifiers remain.",
      { exact: true },
    )
    .waitFor();
  const download = page.waitForEvent("download");
  await lessons
    .getByRole("button", { name: "Export my lessons", exact: true })
    .click();
  assert.equal(
    (await download).suggestedFilename(),
    "veya-reviewed-lessons.json",
  );
  await page.getByRole("button", { name: "Work", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Open task: Fixture lesson attribution",
      exact: true,
    })
    .click();
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  await page
    .getByText(
      "Lesson text unavailable: erased_by_owner. Its contribution remains recorded.",
      { exact: true },
    )
    .waitFor();
  await a11y("erased historical contribution");
  await page.screenshot({
    path: path.join(output, "memory-attribution.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", {
      name: "Open task: Fixture budget failure",
      exact: true,
    })
    .click();
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  await page
    .getByRole("button", { name: "Propose lesson from failure", exact: true })
    .click();
  await page
    .getByText(
      "Candidate saved. Open Data review → Reviewed lessons to edit and approve it.",
      { exact: true },
    )
    .waitFor();
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(output, "browser-checks.txt"),
    "PASS: real Angular → Go → Python memory review, approval, stale revision draft preservation, retraction, erasure, JSON export, historical attribution, keyboard activation and axe at 1440/375. Synthetic fixtures; no live model or native QA claim.\n",
  );
  console.log("Memory browser checks passed.");
} catch (error) {
  await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
  await writeFile(path.join(output,'failure.txt'),await page.locator('body').innerText());
  throw error;
} finally {
  await browser.close();
  child.stdin.end();
  await Promise.race([
    exit,
    new Promise((resolve) =>
      setTimeout(() => {
        child.kill();
        resolve();
      }, 5000),
    ),
  ]);
}
