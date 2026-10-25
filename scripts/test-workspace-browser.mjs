// Real browser checks at the native IPC seam. Fixtures never enter the app bundle.
import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';
import axe from 'axe-core';

const output = path.resolve('artifacts/workspace-design');
await mkdir(output, {recursive:true});
const html = await readFile('apps/desktop/dist/index.html','utf8');
const tasks = [
  ['supplier','Reconcile Northstar supplier invoice','Compare invoice INV-2084 with the purchase order and receiving report. Explain any quantity mismatch before proposing a resolution.','waiting'],
  ['renewal','Prepare the October renewal summary','Summarize upcoming renewals, notice periods, and the decisions needed from our team.','running'],
  ['receipts','Check missing delivery receipts','Find the missing receiving documents for the three outstanding supplier orders.','queued'],
  ['expenses','Review the travel expense policy','Compare the current policy with the proposed changes and identify the exceptions.','succeeded'],
  ['contracts','Compare the two contract revisions','The document could not be read. Retain the brief for another attempt.','failed'],
  ['archive','Organize the supplier handover','Prepare a concise index of the handover documents for operations.','cancelled'],
].map(([id,title,instruction,state])=>({id,title,instruction,state,created_at:'2026-10-24T12:00:00Z'}));
const fixture = `
const tasks=${JSON.stringify(tasks)};
const submissions=new Map();
window.__TAURI__={core:{invoke:async(command,{operation,args}={})=>{
  if(command==='runtime_health'||command==='runtime_restart')return {state:'ready',message:'Interface test connection. Sample data only.'};
  if(operation==='recovery')return {required:false};
  if(operation==='list_tasks')return {items:tasks.slice(0,10),next_cursor:null};
  if(operation==='submit_task'){
    if(!submissions.has(args.client_request_id)){const task={id:args.client_request_id,title:args.title,instruction:args.instruction,state:'queued',created_at:new Date().toISOString()};tasks.unshift(task);submissions.set(args.client_request_id,{task,run:{id:'run_'+task.id,state:'queued'}});}
    return submissions.get(args.client_request_id);
  }
  if(operation==='latest_run'){const task=tasks.find(t=>t.id===args.task_id);return {id:'run_'+task.id,state:task.state};}
  if(operation==='events')return {items:args.after?[]:[{run_id:args.run_id,sequence:1,kind:'task.created',data:{message:'Task saved. This is an interface test event.'},created_at:'2026-10-24T12:00:00Z'}],next_cursor:args.after||args.run_id+':1',has_more:false};
  throw Error('Unexpected fixture operation: '+operation);
}}};
`;
const fixtureHtml = html.replace('<head>', '<head><script src="/fixture.js"></script>').replace('<body>', '<body><div style="padding:5px 16px;background:#eef3ed;color:#315c48;font:12px sans-serif">Interface test · Sample tasks · No live execution</div>');
const server = http.createServer(async(req,res)=>{
  try {
    const url=new URL(req.url,'http://localhost');
    if(url.pathname==='/fixture.js'){res.setHeader('Content-Type','text/javascript');res.end(fixture);return;}
    if(url.pathname==='/'||url.pathname==='/fixture'){res.setHeader('Content-Type','text/html');res.end(url.pathname==='/fixture'?fixtureHtml:html);return;}
    const name=path.basename(url.pathname);
    if(url.pathname!==`/assets/${name}`){res.writeHead(404).end();return;}
    const types={'.css':'text/css','.js':'text/javascript','.woff2':'font/woff2'};
    res.setHeader('Content-Type',types[path.extname(name)]||'application/octet-stream');
    res.end(await readFile(path.join('apps/desktop/dist/assets',name)));
  } catch {res.writeHead(404).end();}
});
await new Promise(resolve=>server.listen(Number(process.env.VEYA_PREVIEW_PORT||0),'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
if(process.argv.includes('--serve')){
  console.log(`Labelled interface fixture: ${origin}/fixture\nDisconnected browser preview: ${origin}/`);
} else {
  const browser=await chromium.launch({executablePath:process.env.VEYA_CHROME||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':undefined),headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const checks=[];
  async function screenshot(name){await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});}
  async function accessibility(label){
    await page.evaluate(axe.source);
    const result=await page.evaluate(()=>window.axe.run(document.querySelector('.veya-workspace'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));
    assert.deepEqual(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],label);
    checks.push(`${label}: axe WCAG A/AA checks passed`);
  }
  try {
    await page.goto(origin+'/fixture');
    await page.locator('.work-table tbody tr').nth(5).waitFor();
    await page.evaluate(()=>document.fonts.ready);
    assert.ok(await page.locator('.veya-workspace').evaluate(el=>getComputedStyle(el).fontFamily.includes('Public Sans')));
    await screenshot('work-wide');await accessibility('Work list');
    await page.getByRole('button',{name:'Expand navigation',exact:true}).click();
    await page.getByRole('button',{name:'Collapse navigation',exact:true}).waitFor();
    await page.reload();await page.getByRole('button',{name:'Collapse navigation',exact:true}).waitFor();
    await page.getByRole('button',{name:'Collapse navigation',exact:true}).click();
    await page.getByRole('searchbox',{name:'Search recent work'}).fill('notice periods');
    await page.waitForFunction(()=>document.querySelectorAll('.work-table tbody tr').length===1);
    await page.getByRole('searchbox',{name:'Search recent work'}).fill('');
    await page.getByRole('button',{name:/Needs attention/}).click();
    assert.equal(await page.locator('.work-table tbody tr').count(),2);
    const opener=page.getByRole('button',{name:'Open task: Reconcile Northstar supplier invoice',exact:true});
    await opener.click();await page.getByRole('dialog',{name:'Task details'}).waitFor();
    await screenshot('task-overview');await accessibility('Task overview');
    await page.getByRole('tab',{name:'Overview',exact:true}).focus();await page.keyboard.press('ArrowRight');
    await page.getByRole('heading',{name:'Recorded activity',exact:true}).waitFor();
    assert.equal(await page.getByRole('tab',{name:'Activity',exact:true}).getAttribute('aria-selected'),'true');
    await screenshot('task-activity');await accessibility('Task activity');
    for(let i=0;i<10;i++){await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>Boolean(document.activeElement?.closest('dialog[open]'))),'modal contains keyboard focus');}
    await page.keyboard.press('Escape');await page.getByRole('dialog',{name:'Task details'}).waitFor({state:'hidden'});
    assert.ok(await opener.evaluate(el=>el===document.activeElement),'Escape restores task focus');
    assert.equal(await page.getByRole('button',{name:/Needs attention/}).getAttribute('aria-pressed'),'true');
    await page.getByRole('button',{name:'New task',exact:true}).click();
    await page.getByLabel('Task name',{exact:true}).fill('A preserved draft');
    await page.getByLabel('What would you like done?',{exact:true}).fill('Keep this brief while I inspect other work.');
    await screenshot('composer');await accessibility('Task editor');
    await page.keyboard.press('Escape');await page.getByRole('button',{name:'New task',exact:true}).click();
    assert.equal(await page.getByLabel('Task name',{exact:true}).inputValue(),'A preserved draft');
    await page.getByRole('button',{name:'Save task',exact:true}).click();
    await page.getByRole('heading',{name:'A preserved draft',exact:true}).waitFor();
    assert.equal(await page.getByRole('tab',{name:'Activity',exact:true}).getAttribute('aria-selected'),'true');
    await page.keyboard.press('Escape');await page.getByRole('button',{name:/All work/}).click();
    await page.evaluate(()=>{const t=document.querySelector('.work-task-link span');t.textContent='VeryLongSupplierReference'.repeat(14);});
    for(const width of [800,375]){
      await page.setViewportSize({width,height:800});
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow at '+width);
      await screenshot('work-'+width);
      await page.getByRole('button',{name:'New task',exact:true}).click();
      assert.ok(await page.getByRole('button',{name:'Save task',exact:true}).isVisible());
      await page.getByRole('button',{name:'Save task',exact:true}).scrollIntoViewIfNeeded();
      assert.ok(await page.evaluate(()=>document.querySelector('dialog[open]').scrollWidth<=document.querySelector('dialog[open]').clientWidth),'editor has no horizontal overflow');
      await page.keyboard.press('Escape');
    }
    await page.setViewportSize({width:800,height:640});
    await page.getByRole('button',{name:'New task',exact:true}).click();await screenshot('composer-minimum');
    await page.getByRole('button',{name:'Save task',exact:true}).scrollIntoViewIfNeeded();
    assert.ok(await page.getByRole('button',{name:'Save task',exact:true}).evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}),'save is reachable at the native minimum window size');
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:1440,height:1000});await page.goto(origin+'/');
    await page.getByRole('heading',{name:'Your work starts here'}).waitFor();
    await screenshot('empty-browser');await accessibility('Disconnected empty workspace');
    await page.getByRole('button',{name:'New task',exact:true}).click();
    assert.ok(await page.getByRole('button',{name:'Save task',exact:true}).isDisabled());
    assert.deepEqual(errors,[]);
    checks.push('PASS: navigation persistence, search, filters, Overview/Activity keyboard tabs, modal focus containment/restoration, draft close/reopen, submit opens activity, narrow and minimum windows, long title wrapping, disabled browser submission; no page errors.');
    await writeFile(path.join(output,'browser-checks.txt'),checks.join('\n')+'\n');console.log(checks.join('\n'));
  } catch (error) {
    await screenshot('failed-check');
    console.error('Browser errors:',errors,'Visible page:',await page.locator('body').innerText());
    throw error;
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
}
