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
  output = "artifacts/document-batch";
await mkdir(output, { recursive: true });
const storage = await mkdtemp(path.join(root, output, "workspace-"));
const python =
  process.env.VEYA_PYTHON ||
  path.join(
    root,
    "services/runtime/.venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const seed = spawnSync(python, ["scripts/seed_document_fixture.py", storage], {
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
      name: "Open task: Fixture completed order",
      exact: true,
    })
    .waitFor();
  await command("New task");
  await page
    .getByLabel("Task name", { exact: true })
    .fill("Fixture document review");
  await page
    .getByLabel("What would you like done?", { exact: true })
    .fill("Inspect these source records.");
  const input = page.getByLabel("Add document files", { exact: true });
  await input.setInputFiles({
    name: "disguised.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("MZexecutable"),
  });
  await page
    .getByText("This file could not be imported.", { exact: false })
    .waitFor();
  assert.ok(
    await page
      .getByRole("button", { name: "Save task", exact: true })
      .isDisabled(),
  );
  await page
    .getByRole("button", { name: "Remove disguised.csv", exact: true })
    .click();
  const file = {
    name: "Order.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "date,quantity,currency,amount\n2026-10-25,1.250,USD,12.30\n",
    ),
  };
  await input.setInputFiles(file);
  await page.waitForFunction(() =>
    document
      .querySelector(".work-document-list")
      ?.textContent.includes("ready"),
  );
  await input.setInputFiles(file);
  await page
    .getByText("This document is already attached.", { exact: true })
    .waitFor();
  assert.equal(await page.locator(".work-document-list>li").count(), 1);
  await page
    .getByRole("button", { name: "Inspect Order.csv", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Order.csv", exact: true }).waitFor();
  await page.getByText("1.250", { exact: true }).waitFor();
  await a11y("Source inspection");
  await page.screenshot({
    path: output + "/source-desktop.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page
    .getByRole("dialog", { name: "Source document" })
    .waitFor({ state: "hidden" });
  await page.waitForFunction(
    () => document.activeElement.textContent.trim() === "Inspect Order.csv",
  );
  await page.screenshot({
    path: output + "/attachments-desktop.png",
    fullPage: true,
  });
  await a11y("Attachment composer");
  // Closing while restored documents load must retain every saved attachment.
  const draftBefore = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("veya-task-draft-v1")),
  );
  await page.keyboard.press("Escape");
  let releaseHydration;
  const hydrationGate = new Promise((resolve) => {
    releaseHydration = resolve;
  });
  let hydrationSeen;
  const hydrationStarted = new Promise((resolve) => {
    hydrationSeen = resolve;
  });
  let hydrationFinished;
  const hydrationComplete = new Promise((resolve) => {
    hydrationFinished = resolve;
  });
  const delayHydration = async (route) => {
    if (route.request().postDataJSON().operation === "get_document") {
      hydrationSeen();
      await hydrationGate;
      await route.continue();
      hydrationFinished();
    } else await route.fallback();
  };
  await page.route("**/api/workspace", delayHydration);
  try {
    await command("New task");
    await Promise.race([
      hydrationStarted,
      new Promise((_, reject) =>
        setTimeout(() => reject(Error("No hydration request")), 5000),
      ),
    ]);
    await page.keyboard.press("Escape");
    assert.deepEqual(
      await page.evaluate(
        () =>
          JSON.parse(localStorage.getItem("veya-task-draft-v1")).document_ids,
      ),
      draftBefore.document_ids,
    );
  } finally {
    releaseHydration();
    await hydrationComplete;
    await page.unroute("**/api/workspace", delayHydration);
  }
  await command("New task");
  await page.waitForFunction(() =>
    document
      .querySelector(".work-document-list")
      ?.textContent.includes("ready"),
  );
  await page.getByRole("button", { name: "Save task", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page
    .getByRole("heading", { name: "Fixture document review", exact: true })
    .waitFor();
  await page.getByRole("tab", { name: "Overview", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page
    .getByRole("button", { name: "Inspect Order.csv", exact: true })
    .waitFor();
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", {
      name: "Open task: Fixture completed order",
      exact: true,
    })
    .click();
  await page.getByRole("tab", { name: "Overview", exact: true }).focus();
  await page.keyboard.press("End");
  await page
    .getByText("The fixture amount is 12.30 USD.", { exact: true })
    .waitFor();
  await page
    .getByText("Source evidence unavailable", { exact: true })
    .waitFor();
  await page
    .getByText("Supplier confirmation is outstanding.", { exact: true })
    .waitFor();
  await a11y("Results");
  await page.screenshot({
    path: output + "/results-desktop.png",
    fullPage: true,
  });
  const source = page.getByRole("button", {
    name: /Fixture order.csv.*CSV!A2/,
  });
  await source.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("dialog", { name: "Source evidence" }).waitFor();
  await page.getByText("12.30", { exact: true }).waitFor();
  await a11y("Citation");
  await page.keyboard.press("Escape");
  await page
    .getByRole("dialog", { name: "Source evidence" })
    .waitFor({ state: "hidden" });
  await page.waitForFunction(
    () =>
      document.activeElement === document.querySelector(".work-claim button"),
  );
  for (const viewport of [
    { width: 800, height: 640 },
    { width: 375, height: 812 },
    { width: 320, height: 640 },
  ]) {
    await page.setViewportSize(viewport);
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    );
    const exception = page.getByText("Supplier confirmation is outstanding.", {
      exact: true,
    });
    await exception.scrollIntoViewIfNeeded();
    await page.waitForFunction(() => {
      const item = [...document.querySelectorAll("li")].find(
        (el) =>
          el.textContent.trim() === "Supplier confirmation is outstanding.",
      );
      const bounds = item?.getBoundingClientRect();
      return bounds && bounds.y >= 0 && bounds.bottom <= innerHeight + 1;
    });
    await page.screenshot({
      path: output + `/results-${viewport.width}.png`,
      fullPage: false,
    });
    await a11y("Results " + viewport.width);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.keyboard.press("Escape");
  await command("New task");
  await page
    .getByLabel("Task name", { exact: true })
    .fill("Fixture lost submission response");
  await page
    .getByLabel("What would you like done?", { exact: true })
    .fill("Preserve retry identity even when evidence is revoked.");
  await page.getByLabel("Add document files", { exact: true }).setInputFiles({
    name: "Retry.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("amount\n5.00\n"),
  });
  await page.waitForFunction(() =>
    document
      .querySelector(".work-document-list")
      ?.textContent.includes("ready"),
  );
  let dropped = false;
  await page.route("**/api/workspace", async (route) => {
    const req = route.request().postDataJSON();
    if (req.operation === "submit_task" && !dropped) {
      dropped = true;
      const response = await route.fetch();
      assert.equal(response.status(), 201);
      const revoke = await fetch(origin + "/api/workspace", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          operation: "revoke_document",
          args: { id: req.args.document_ids[0] },
        }),
      });
      assert.equal(revoke.status, 200);
      await route.abort();
    } else await route.fallback();
  });
  await page.getByRole("button", { name: "Save task", exact: true }).click();
  await page
    .getByRole("button", { name: "Retry same task", exact: true })
    .waitFor();
  await page.reload();
  await page.getByRole("button", { name: "New task", exact: true }).click();
  await page
    .getByText("Source access is unavailable.", { exact: false })
    .waitFor();
  assert.ok(
    await page
      .getByRole("button", { name: "Retry same task", exact: true })
      .isEnabled(),
  );
  await page
    .getByRole("button", { name: "Retry same task", exact: true })
    .click();
  await page
    .getByRole("heading", {
      name: "Fixture lost submission response",
      exact: true,
    })
    .waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Commands", exact: false }).focus();
  await page.keyboard.press("Enter");
  await a11y("Commands");
  await page.keyboard.press("Escape");
  await page
    .getByRole("dialog", { name: "Commands" })
    .waitFor({ state: "hidden" });
  await page.waitForFunction(
    () =>
      document.activeElement ===
      document.querySelector(".work-command-trigger"),
  );
  assert.deepEqual(errors, []);
  await writeFile(
    output + "/browser-checks.txt",
    "PASS: real browser file upload, invalid-file removal, deduplication, exact cell inspection, task attachment persistence through interrupted hydration, completed artifact and source citation inspection, missing evidence, keyboard dialogs/commands/focus return, 1440/800/375/320px, axe checks, lost-response replay after source revocation. Synthetic fixtures only; native OS picker and screen-reader listening require manual QA.\n",
  );
  console.log("Document browser flow passed");
} catch (error) {
  await page.screenshot({ path: output + "/failure.png", fullPage: true });
  await writeFile(output + "/failure.html", await page.content());
  console.error(await page.locator("body").innerText());
  throw error;
} finally {
  await browser.close();
  child.stdin.end();
  const timer = setTimeout(() => child.kill(), 8000);
  await exit;
  clearTimeout(timer);
  lines.close();
}
