import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import axe from 'axe-core';
import {harness,isolate} from './browser-harness.mjs';
const h=await harness();
const context=await h.browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',serviceWorkers:'block'});
await isolate(context,h.origin);
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const output='artifacts/workspace-design';await mkdir(output,{recursive:true});
await page.addInitScript(()=>{
  const tasks=Array.from({length:23},(_,i)=>({id:'fixture_'+i,title:'Fixture task '+i,instruction:'Synthetic review brief '+i,state:'waiting',created_at:'2026-10-24T12:00:00Z'}));
  const review={id:'request_1',proposal_id:'proposal_1',operation_key:'invoice_1',policy_version:'policy_1',state:'pending',attention:'due_soon',revision:1,expires_at:Date.now()/1000+3600,expired:false,tool_name:'invoice.update',tool_version:'1.0.0',arguments:{invoice_id:'invoice_123',amount:42},arguments_hash:'a'.repeat(64),run_id:'run_1',context_hash:'b'.repeat(64),policy_reason:'This exact change requires your review.',scope:{tenant_id:'fixture_a',workspace_id:'workspace_a',actor_id:'reviewer_a'}};
  window.fixture={tasks,review,calls:[],conflict:false};
  window.__TAURI__={core:{invoke:async(command,{operation,args}={})=>{
    if(command==='runtime_health')return {state:'ready',message:'Fixture connection'};
    if(operation==='recovery')return {required:false,message:'Some operations need outcome reconciliation. Do not retry them as new work.'};
    if(operation==='get_task'){const task=tasks.find(t=>t.id===args.task_id);if(!task)throw Error('not_found');return task;}
    if(operation==='list_tasks'){
      const groups={attention:['waiting','failed'],active:['running','queued'],completed:['succeeded']};
      let rows=tasks.filter(t=>(!args.status||groups[args.status]?.includes(t.state))&&(!args.search||(t.title+' '+t.instruction).toLowerCase().includes(args.search.toLowerCase())));
      if(args.sort==='oldest')rows=rows.slice().reverse();
      const offset=Number(args.cursor||0);
      return {items:rows.slice(offset,offset+10),next_cursor:rows.length>offset+10?String(offset+10):null};
    }
    if(operation==='latest_run')return {id:'run_'+args.task_id,state:'waiting'};
    if(operation==='events')return {items:[],next_cursor:args.after,has_more:false};
    if(operation==='list_approvals')return {items:review.state==='pending'?[{...review}]:[],next_cursor:null};
    if(operation==='get_approval')return {...review};
    if(operation==='decide_approval'){
      window.fixture.calls.push(args);
      if(window.fixture.conflict)throw Error('conflict');
      if(args.revision!==review.revision)throw Error('conflict');
      review.state=args.decision==='approve'?'approved':'rejected';review.revision++;
      return {...review};
    }
    throw Error('Unexpected fixture command '+operation);
  }}};
});
async function rows(count){await page.waitForFunction(n=>document.querySelectorAll('.work-table tbody tr').length===n,count);}
async function a11y(label){await page.evaluate(axe.source);const r=await page.evaluate(()=>window.axe.run(document.querySelector('.veya-workspace'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}}));assert.deepEqual(r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[],label);}
try {
  await page.goto(h.origin);await rows(10);
  await page.getByText('Some operations need outcome reconciliation. Do not retry them as new work.',{exact:true}).waitFor();
  assert.equal(await page.locator('.work-table tbody td').first().evaluate(e=>getComputedStyle(e).paddingTop),'14px');
  await page.getByRole('button',{name:'Needs attention',exact:true}).click();
  await page.getByRole('combobox',{name:'Sort',exact:true}).selectOption('oldest');
  await page.getByRole('button',{name:'Open task: Fixture task 22',exact:true}).waitFor();
  await page.getByRole('button',{name:'Next',exact:true}).click();await page.getByRole('button',{name:'Open task: Fixture task 12',exact:true}).click();
  await page.getByRole('dialog',{name:'Task details'}).waitFor();
  await page.reload();await page.getByRole('heading',{name:'Fixture task 12',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('combobox',{name:'Sort',exact:true}).inputValue(),'oldest');
  assert.equal(await page.getByRole('button',{name:'Needs attention',exact:true}).getAttribute('aria-pressed'),'true');
  await page.getByRole('button',{name:'Next',exact:true}).click();
  await page.getByRole('button',{name:'Open task: Fixture task 12',exact:true}).waitFor();
  await page.evaluate(()=>window.fixture.tasks.splice(0,13));
  await page.getByRole('button',{name:'Refresh',exact:true}).click();await rows(10);
  await page.getByRole('button',{name:'Open task: Fixture task 22',exact:true}).waitFor();
  assert.ok(await page.getByRole('button',{name:'Previous',exact:true}).isDisabled());
  assert.equal(await page.getByRole('button',{name:'Needs attention',exact:true}).getAttribute('aria-pressed'),'true');
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:output+'/queue-paged.png',fullPage:true});await a11y('Paged queue');
  await page.getByRole('button',{name:'Approvals',exact:true}).click();
  const opener=page.getByRole('button',{name:/Review operation invoice_1/});await opener.click();
  await page.getByRole('heading',{name:'invoice.update',exact:true}).waitFor();
  assert.ok((await page.locator('.review-arguments').innerText()).includes('invoice_123'));
  assert.ok(await page.getByRole('button',{name:'Approve operation',exact:true}).isDisabled());
  await page.getByLabel('Decision note',{exact:true}).fill('Reviewed the exact invoice');
  await page.screenshot({path:output+'/approval-review.png',fullPage:true});await a11y('Exact approval review');
  await page.evaluate(()=>window.fixture.conflict=true);
  await page.getByRole('button',{name:'Approve operation',exact:true}).click();
  await page.getByText('This request changed or expired. Refresh it before deciding.',{exact:false}).waitFor();
  assert.equal(await page.evaluate(()=>window.fixture.calls.length),1);
  await page.evaluate(()=>{window.fixture.review.state='superseded';window.fixture.review.expired=true;window.fixture.review.revision++;});
  await page.getByRole('button',{name:'Refresh this review',exact:true}).click();
  await page.getByText('This request is no longer current. Request a fresh review.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Approve operation',exact:true}).count(),0);
  await page.keyboard.press('Escape');assert.ok(await opener.evaluate(e=>e===document.activeElement));
  await page.evaluate(()=>{window.fixture.conflict=false;Object.assign(window.fixture.review,{state:'pending',expired:false,revision:3,expires_at:Date.now()/1000+1.5});});
  await opener.click();await page.getByLabel('Decision note',{exact:true}).fill('Deadline test');
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Approve operation')?.disabled);
  assert.equal(await page.evaluate(()=>window.fixture.calls.length),1);
  await page.keyboard.press('Escape');
  await page.evaluate(()=>window.fixture.review.expires_at=Date.now()/1000+3600);
  await opener.click();await page.getByLabel('Decision note',{exact:true}).fill('Reject after current evidence review');
  await page.getByRole('button',{name:'Reject operation',exact:true}).click();await page.getByText('Rejection recorded.',{exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(()=>window.fixture.calls.at(-1)),{id:'request_1',revision:3,decision:'reject',note:'Reject after current evidence review'});
  for(const width of [800,375]){
    await page.setViewportSize({width,height:640});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.ok(await page.evaluate(()=>{const d=document.querySelector('dialog[open]');return d.scrollWidth<=d.clientWidth;}));
    await a11y('Review at '+width);
  }
  await page.keyboard.press('Escape');await page.getByRole('heading',{name:'No decisions waiting',exact:true}).waitFor();
  // Request interception fails before a DNS lookup or connector request can occur.
  assert.equal(await page.evaluate(async()=>{try{await fetch('https://fixture-external.invalid/live');return false;}catch{return true;}}),true);
  assert.deepEqual(errors,[]);
  const result='PASS: queue paging, empty-page recovery, filter/sort/selection restoration, 14px rows, uncertainty notice, exact approval arguments, required notes, stale revision, expiry without dispatch, reject decision identity, keyboard focus restoration, narrow layouts, axe accessibility and external-network denial.';
  await writeFile(output+'/batch15-browser-checks.txt',result+'\n');console.log(result);
} catch(error){await page.screenshot({path:output+'/batch15-failure.png',fullPage:true});console.error(await page.locator('body').innerText());throw error;}
finally{await context.close();await h.close();}
