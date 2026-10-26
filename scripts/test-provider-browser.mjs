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
import { createServer } from "node:http";
const root = process.cwd(),
  output = "artifacts/provider-batch";
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
const provider = createServer(async (req, res) => {
  if (req.url === "/v1/models") {
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ data: [{ id: "fixture-tools" }] }));
    return;
  }
  if (req.url !== "/v1/chat/completions") {
    res.writeHead(404).end();
    return;
  }
  let raw = "";
  for await (const part of req) raw += part;
  const input = JSON.parse(raw),
    check = input.tools?.[0]?.function.name === "connection_check";
  const observed = input.messages.some((m) => m.role === "tool");
  const delta =
    check || !observed
      ? {
          tool_calls: [
            {
              index: 0,
              id: "call_fixture",
              type: "function",
              function: {
                name: check ? "connection_check" : "calculate",
                arguments: JSON.stringify(
                  check
                    ? { value: "ready" }
                    : { left: "120", right: "12.30", operation: "multiply" },
                ),
              },
            },
          ],
        }
      : {
          content: JSON.stringify({
            summary: "Synthetic calculation complete",
            citations: [],
            exceptions: [],
          }),
        };
  res.writeHead(200, { "Content-Type": "text/event-stream" });
  res.end(
    "data: " +
      JSON.stringify({ choices: [{ index: 0, delta, finish_reason: null }] }) +
      "\n\ndata: " +
      JSON.stringify({
        choices: [
          {
            index: 0,
            delta: {},
            finish_reason: check || !observed ? "tool_calls" : "stop",
          },
        ],
      }) +
      "\n\ndata: [DONE]\n\n",
  );
});
await new Promise((resolve) => provider.listen(0, "127.0.0.1", resolve));
const modelEndpoint = `http://127.0.0.1:${provider.address().port}/v1`;
try {
  await page.goto(origin + "/#session=" + token);
  await page
    .getByRole("button", {
      name: "Open task: Fixture completed order",
      exact: true,
    })
    .waitFor();
  await command("Connection");
  await page.getByLabel("Endpoint", { exact: true }).fill(modelEndpoint);
  await page
    .getByLabel("Installed model name", { exact: true })
    .fill("fixture-tools");
  await page
    .getByLabel("Model context limit (tokens)", { exact: true })
    .fill("32768");
  await page
    .getByRole("button", { name: "Test and save connection", exact: true })
    .click();
  await page
    .getByText("Connection passed. Choose Use provider to activate it.", {
      exact: true,
    })
    .waitFor();
  await page
    .getByRole("button", { name: "Use provider local", exact: true })
    .click();
  await page
    .getByText("Active order: fixture-tools", { exact: true })
    .waitFor();
  for (const width of [1440, 800, 375, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await a11y("Connection " + width);
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      "Connection fits viewport",
    );
    await page.screenshot({
      path: output + `/connection-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => (document.documentElement.style.zoom = "2"));
  await page
    .getByRole("button", { name: "Test and save connection", exact: true })
    .scrollIntoViewIfNeeded();
  await a11y("Connection at 200 percent CSS zoom");
  await page.screenshot({
    path: output + "/connection-zoom200.png",
    fullPage: true,
  });
  await page.evaluate(() => (document.documentElement.style.zoom = "1"));
  await page
    .getByLabel("Installed model name", { exact: true })
    .fill("not-installed");
  await page
    .getByRole("button", { name: "Test and save connection", exact: true })
    .click();
  await page.locator("#provider-error").waitFor();
  assert.ok(
    await page
      .getByText("Active order: fixture-tools", { exact: true })
      .isVisible(),
  );
  await page.keyboard.press("Escape");
  await command("New task");
  await page
    .getByLabel("Task name", { exact: true })
    .fill("Fixture provider calculation");
  await page
    .getByLabel("What would you like done?", { exact: true })
    .fill("Multiply 120 by 12.30 using the exact calculator.");
  await page.getByRole("button", { name: "Save task", exact: true }).click();
  await page
    .getByRole("button", { name: "Start read-only task", exact: true })
    .click();
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await page
    .getByRole("heading", { name: "Read-only result.json", exact: true })
    .waitFor({ timeout: 20000 });
  await a11y("Executed task results");
  await page.screenshot({
    path: output + "/executed-task.png",
    fullPage: true,
  });
  await page
    .getByText("120 multiply 12.30 = 1476.00", { exact: true })
    .waitFor();
  if (process.env.VEYA_LIVE_MODEL) {
    await page.keyboard.press("Escape");
    await command("Connection");
    await page
      .getByLabel("Connection name", { exact: true })
      .fill("ollama_validation");
    await page
      .getByLabel("Endpoint", { exact: true })
      .fill("http://127.0.0.1:11434/v1");
    await page
      .getByLabel("Installed model name", { exact: true })
      .fill(process.env.VEYA_LIVE_MODEL);
    await page
      .getByLabel("Model context limit (tokens)", { exact: true })
      .fill("4096");
    await page
      .getByRole("button", { name: "Test and save connection", exact: true })
      .click();
    await page
      .getByText("Connection passed. Choose Use provider to activate it.", {
        exact: true,
      })
      .waitFor();
    await page.screenshot({
      path: output + "/live-ollama-connection.png",
      fullPage: true,
    });
    await writeFile(
      output + "/live-browser-check.txt",
      "PASS: real local Ollama streaming tool probe through Angular, Go and Python; model " +
        process.env.VEYA_LIVE_MODEL +
        ". This is connectivity evidence, not task-quality qualification.\n",
    );
  }
  assert.deepEqual(errors, []);
  await writeFile(
    output + "/browser-checks.txt",
    "PASS: Angular -> Go -> Python -> HTTP fixture provider streaming/tool calls -> durable result; tested activation, failed candidate preserves active provider, keyboard navigation, 1440/800/375/320px and axe. Synthetic provider only.\n",
  );
  console.log("Provider browser flow passed");
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
  provider.closeAllConnections();
  await new Promise((resolve) => provider.close(resolve));
}
