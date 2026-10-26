import {isolate} from './browser-harness.mjs';
// No IPC fixtures: Angular -> Go session/commands -> Python -> SQLite -> Angular.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';
import { once } from 'node:events';
import { chromium } from 'playwright-core';

const root = process.cwd();
await mkdir('artifacts/stack-migration', { recursive: true });
const storage = await mkdtemp(path.join(root, 'artifacts/stack-migration/workspace-'));
const executable = path.join(
  root,
  'apps/desktop/src-tauri/binaries',
  process.platform === 'win32' ? 'veya-platform.exe' : 'veya-platform',
);
const python =
  process.env.VEYA_PYTHON ||
  path.join(
    root,
    'services/runtime/.venv',
    process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
  );
async function start() {
  const token = randomBytes(32).toString('hex');
  const child = spawn(
    executable,
    [
      '--python',
      python,
      '--runtime',
      path.join(root, 'services/runtime'),
      '--assets',
      path.join(root, 'apps/desktop/dist'),
    ],
    { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true },
  );
  const exit = once(child, 'exit');
  const lines = readline.createInterface({ input: child.stdout });
  const ready = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill();
      reject(Error('Platform readiness timeout'));
    }, 16000);
    lines.once('line', (line) => {
      clearTimeout(timer);
      try {
        resolve(JSON.parse(line));
      } catch {
        reject(Error('Invalid readiness'));
      }
    });
    child.once('error', (e) => {
      clearTimeout(timer);
      reject(e);
    });
    child.once('exit', () => {
      clearTimeout(timer);
      reject(Error('Platform exited before readiness'));
    });
  });
  child.stdin.write(
    JSON.stringify({ protocol: 1, storage_root: storage, session_token: token }) + '\n',
  );
  const result = await ready;
  assert.equal(result.protocol, 1);
  assert.equal(result.status, 'ready');
  return {
    origin: `http://127.0.0.1:${result.port}`,
    token,
    close: async () => {
      child.stdin.end();
      const timer = setTimeout(() => child.kill(), 8000);
      await exit;
      clearTimeout(timer);
      lines.close();
    },
  };
}
let platform = await start();
const browser = await chromium.launch({
  executablePath:
    process.env.VEYA_CHROME ||
    (process.platform === 'win32'
      ? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
      : undefined),
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await isolate(page.context(), platform.origin);
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
try {
  assert.equal((await fetch(platform.origin + '/api/health')).status, 401);
  await page.goto(platform.origin + '/#session=' + platform.token);
  await page.waitForFunction(
    () => document.querySelector('.work-connection-button')?.textContent.trim() === 'Connected',
  );
  assert.equal(new URL(page.url()).hash, '');
  assert.equal(await page.evaluate(() => Boolean(window.__TAURI__)), false);
  const cookie = (await page.context().cookies()).find((c) => c.name === 'veya_session');
  assert.ok(cookie?.httpOnly);
  assert.equal(cookie.sameSite, 'Strict');
  await page.getByRole('button', { name: 'New task', exact: true }).click();
  await page.getByLabel('Task name', { exact: true }).fill('Verify the migrated platform');
  await page
    .getByLabel('What would you like done?', { exact: true })
    .fill('Save this brief through Angular and Go, then preserve it across restart.');
  await page.getByRole('button', { name: 'Save task', exact: true }).click();
  await page.getByRole('heading', { name: 'Verify the migrated platform', exact: true }).waitFor();
  await page.getByText('Saved and queued. Test and activate a model in Connection to start this task.').waitFor();
  await page.getByText('No execution activity has been recorded.', { exact: true }).waitFor();
  await page.screenshot({ path: 'artifacts/stack-migration/live-web-task.png', fullPage: true });
  const csrf = await fetch(platform.origin + '/api/workspace', {
    method: 'POST',
    headers: { Cookie: `veya_session=${cookie.value}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ operation: 'list_tasks', args: {} }),
  });
  assert.equal(csrf.status, 401);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'New task', exact: true }).click();
  await page.getByLabel('Task name', { exact: true }).fill('Preserve a draft over restart');
  await page
    .getByLabel('What would you like done?', { exact: true })
    .fill('Keep this exact retry identity through a lost response and restart.');
  const retained = await page.evaluate(() =>
    JSON.parse(localStorage.getItem('veya-task-draft-v1')),
  );
  const oldOrigin = platform.origin;
  await platform.close();
  await assert.rejects(() => fetch(oldOrigin + '/api/health'));
  platform = await start();
  assert.equal(platform.origin, oldOrigin, 'drafts require a stable workspace origin');
  await page.goto(platform.origin + '/#session=' + platform.token);
  await page
    .getByRole('button', { name: 'Open task: Verify the migrated platform', exact: true })
    .waitFor();
  assert.equal(await page.locator('.work-table tbody tr').count(), 1);
  await page.getByRole('button', { name: 'New task', exact: true }).click();
  assert.equal(await page.getByLabel('Task name', { exact: true }).inputValue(), retained.title);
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem('veya-task-draft-v1')).client_request_id,
    ),
    retained.client_request_id,
  );
  let dropped = false;
  await page.route('**/api/workspace', async (route) => {
    if (!dropped && route.request().postDataJSON()?.operation === 'submit_task') {
      dropped = true;
      const response = await route.fetch();
      assert.equal(response.status(), 201);
      await route.abort('failed');
    } else await route.continue();
  });
  await page.getByRole('button', { name: 'Save task', exact: true }).click();
  await page.getByRole('button', { name: 'Retry same task', exact: true }).waitFor();
  await platform.close();
  platform = await start();
  assert.equal(platform.origin, oldOrigin);
  await page.goto(platform.origin + '/#session=' + platform.token);
  await page
    .getByRole('button', { name: 'Open task: Preserve a draft over restart', exact: true })
    .waitFor();
  await page.getByRole('button', { name: 'New task', exact: true }).click();
  assert.equal(await page.getByLabel('Task name', { exact: true }).getAttribute('readonly'), '');
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem('veya-task-draft-v1')).client_request_id,
    ),
    retained.client_request_id,
  );
  await page.getByRole('button', { name: 'Retry same task', exact: true }).click();
  await page.getByRole('heading', { name: retained.title, exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => document.querySelectorAll('.work-table tbody tr').length === 2);
  await page.screenshot({
    path: 'artifacts/stack-migration/live-web-restarted.png',
    fullPage: true,
  });
  assert.deepEqual(errors, []);
  const message =
    'PASS: real Angular/Go/Python task creation, honest empty activity, HttpOnly session, fragment removal, CSRF rejection, parent EOF shutdown, closed listener, stable origin, unsent draft and ambiguous submission identity across two restarts, no duplicate after retry; no browser errors.';
  await writeFile('artifacts/stack-migration/web-checks.txt', message + '\n');
  console.log(message);
} catch (error) {
  await page.screenshot({ path: 'artifacts/stack-migration/web-failed.png', fullPage: true });
  console.error(await page.locator('body').innerText());
  throw error;
} finally {
  await browser.close();
  await platform.close();
}
