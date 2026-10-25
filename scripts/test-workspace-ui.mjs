// Built Angular integration at the IPC boundary, in Chromium rather than React/jsdom.
import assert from 'node:assert/strict';
import { harness, isolate } from './browser-harness.mjs';
const h = await harness();
const errors = [];
async function boot(mode) {
  const context = await h.browser.newContext(),
    page = await context.newPage();
  await isolate(context,h.origin);
  page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript((mode) => {
    const task = {
        id: 'task_demo',
        title: 'Review <script> order',
        instruction: 'Local fixture instruction',
        state: 'queued',
        created_at: '2026-10-24T12:00:00Z',
      },
      run = { id: 'run_demo', state: 'queued' };
    window.fixture = { submissions: [], cursors: [], state: 'ready', recoveryCalls: 0 };
    let saved = false,
      eventCount = 0;
    window.__TAURI__ = {
      core: {
        invoke: async (command, { operation, args } = {}) => {
          const f = window.fixture;
          if (command === 'runtime_health' || command === 'runtime_restart')
            return { state: f.state, message: 'Test connection' };
          if (operation === 'recovery') {
            f.recoveryCalls++;
            if (mode === 'reconnect' && f.recoveryCalls > 1)
              return new Promise((resolve) => (f.releaseRecovery = resolve));
            return { required: mode === 'readonly' };
          }
          if (operation === 'list_tasks')
            return {
              items:
                mode === 'readonly'
                  ? (args.status === 'attention' && task.state === 'running' ? [] : [{ ...task, id: 'waiting', state: task.state === 'running' ? 'running' : 'waiting' }])
                  : saved
                    ? [task]
                    : [],
              next_cursor: null,
            };
          if (operation === 'submit_task') {
            f.submissions.push(args);
            await new Promise((r) => setTimeout(r, 80));
            if (mode === 'invalid') throw 'invalid_input';
            saved = true;
            if (f.submissions.length === 1) throw 'runtime_timeout';
            return { task, run };
          }
          if (operation === 'latest_run') {
            if(mode === 'readonly') task.state='running';
            return mode === 'readonly' ? { ...run, state: 'running' } : run;
          }
          if (operation === 'events') {
            f.cursors.push(args.after);
            if (eventCount++ === 0)
              return {
                items: [
                  {
                    run_id: run.id,
                    sequence: 1,
                    kind: 'model.partial',
                    data: { message: 'Partial response only' },
                    created_at: task.created_at,
                  },
                ],
                next_cursor: 'run_demo:1',
                has_more: false,
              };
            return { items: [], next_cursor: args.after, has_more: false };
          }
          throw Error('Unexpected operation');
        },
      },
    };
  }, mode);
  await page.goto(h.origin);
  await page.waitForFunction(() => window.fixture.recoveryCalls === 1);
  return { page, close: () => context.close() };
}
async function compose(p, title = 'Review <script> order') {
  await p.getByRole('button', { name: 'New task', exact: true }).click();
  await p.getByLabel('Task name', { exact: true }).fill(title);
  await p
    .getByLabel('What would you like done?', { exact: true })
    .fill('Local fixture instruction');
}
try {
  const t = await boot('retry'),
    p = t.page;
  await compose(p);
  await p.waitForFunction(() => !document.querySelector('.work-composer button').disabled);
  await p.locator('form').evaluate((f) => {
    for (let i = 0; i < 2; i++)
      f.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
  await p.getByRole('button', { name: 'Retry same task', exact: true }).waitFor();
  assert.equal(await p.evaluate(() => window.fixture.submissions.length), 1);
  assert.equal(await p.getByLabel('Task name', { exact: true }).getAttribute('readonly'), '');
  assert.equal(
    await p.evaluate(
      () => JSON.parse(localStorage.getItem('veya-task-draft-v1')).client_request_id,
    ),
    await p.evaluate(() => window.fixture.submissions[0].client_request_id),
  );
  await p.getByRole('button', { name: 'Retry same task', exact: true }).click();
  await p.getByText('Partial response only', { exact: true }).waitFor();
  const submissions = await p.evaluate(() => window.fixture.submissions);
  assert.equal(submissions.length, 2);
  assert.deepEqual(submissions[0], submissions[1]);
  await p.waitForFunction(() => window.fixture.cursors.includes('run_demo:1'));
  assert.equal(await p.locator('.work-events li').count(), 1);
  assert.equal(await p.locator('.work-activity script').count(), 0);
  assert.equal(await p.locator('#activity-title').innerText(), 'Review <script> order');
  await p.getByText('Saved and queued. AI execution is not connected yet.').waitFor();
  await p.keyboard.press('Escape');
  await compose(p, 'New draft');
  await p.keyboard.press('Escape');
  await p.getByRole('button', { name: 'New task', exact: true }).click();
  assert.equal(await p.getByLabel('Task name', { exact: true }).inputValue(), 'New draft');
  await t.close();
  const invalid = await boot('invalid');
  await compose(invalid.page);
  await invalid.page.getByRole('button', { name: 'Save task', exact: true }).click();
  await invalid.page.getByRole('alert').waitFor();
  assert.equal(
    await invalid.page.getByLabel('Task name', { exact: true }).getAttribute('readonly'),
    null,
  );
  await invalid.page.getByLabel('Task name', { exact: true }).fill('Corrected title');
  assert.equal(
    await invalid.page.evaluate(() => JSON.parse(localStorage.getItem('veya-task-draft-v1')).title),
    'Corrected title',
  );
  await invalid.close();
  const readonly = await boot('readonly'),
    r = readonly.page;
  await r.getByRole('button', { name: /Needs attention/ }).click();
  await r.getByRole('button', { name: 'Open task: Review <script> order', exact: true }).click();
  await r.waitForFunction(() =>
    document.querySelector('.work-detail-heading')?.textContent.includes('In progress'),
  );
  await r.keyboard.press('Escape');
  await r.getByRole('heading', { name: 'No matching work', exact: true }).waitFor();
  await compose(r, 'Read-only draft');
  assert.ok(await r.getByRole('button', { name: 'Save task', exact: true }).isDisabled());
  await readonly.close();
  const reconnect = await boot('reconnect'),
    c = reconnect.page;
  await compose(c, 'Preserve on reconnect');
  await c.waitForFunction(() => !document.querySelector('.work-composer button').disabled);
  await c.evaluate(() => (window.fixture.state = 'failed'));
  await c.waitForFunction(() => document.querySelector('.work-composer button').disabled);
  await c.evaluate(() => (window.fixture.state = 'ready'));
  await c.waitForFunction(() => Boolean(window.fixture.releaseRecovery));
  assert.ok(await c.getByRole('button', { name: 'Save task', exact: true }).isDisabled());
  await c
    .locator('form')
    .evaluate((f) => f.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  assert.equal(await c.evaluate(() => window.fixture.submissions.length), 0);
  await c.evaluate(() => window.fixture.releaseRecovery({ required: true }));
  await c
    .getByText('This workspace is read-only pending recovery review.')
    .waitFor({ state: 'attached' });
  assert.ok(await c.getByRole('button', { name: 'Save task', exact: true }).isDisabled());
  assert.equal(
    await c.getByLabel('Task name', { exact: true }).inputValue(),
    'Preserve on reconnect',
  );
  await reconnect.close();
  assert.deepEqual(errors, []);
  console.log(
    'PASS Angular IPC: duplicate guard, immutable retries, validation correction, escaping, cursor resume, drafts, live status, read-only and reconnect recovery gating.',
  );
} finally {
  await h.close();
}
