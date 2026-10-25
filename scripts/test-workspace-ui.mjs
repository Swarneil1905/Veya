// Built-entry integration at the native IPC seam. No native/visual claims here.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';
const html = readFileSync('apps/desktop/dist/index.html', 'utf8');
const script = html.match(/<script[^>]+src="([^"]+)"[^>]*><\/script>/);
const js = readFileSync(`apps/desktop/dist${script[1]}`, 'utf8');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(test) { for(let i=0;i<100;i++) { if(test()) return; await wait(40); } assert.ok(test(), 'UI condition timed out'); }
function boot(invoke) {
  const dom = new JSDOM(html.replace(script[0], ''), { url: 'http://tauri.localhost', runScripts:'outside-only', pretendToBeVisual:true });
  // Browser modal/focus semantics are exercised separately in rendered tests.
  dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','');};
  dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');};
  if(invoke) dom.window.__TAURI__ = { core: { invoke } };
  dom.window.eval(js);
  return dom;
}
const button=(w,text)=>[...w.document.querySelectorAll('button')].find(b=>b.textContent===text);
function fill(w,id,value) {
  const element = w.document.getElementById(id);
  Object.getOwnPropertyDescriptor(element.tagName === 'TEXTAREA' ? w.HTMLTextAreaElement.prototype : w.HTMLInputElement.prototype,'value').set.call(element,value);
  element.dispatchEvent(new w.Event('input',{bubbles:true}));
}
const created={id:'task_demo',title:'Review <script> order',instruction:'Local fixture instruction',state:'queued',created_at:'2026-10-24T12:00:00Z'};
const run={id:'run_demo',state:'queued'};
let submissions=[], saved=false, failed=false, cursors=[], eventCount=0;
const dom=boot(async(command,{operation,args}={})=>{
  if(command==='runtime_health'||command==='runtime_restart') return {state:'ready',message:'Connected to your local workspace.'};
  if(operation==='recovery')return {required:false};
  if(operation==='list_tasks')return {items:saved?[created]:[],next_cursor:null};
  if(operation==='submit_task'){
    submissions.push(args);saved=true;
    await wait(80);
    if(!failed){failed=true;throw 'runtime_timeout';}
    return {task:created,run};
  }
  if(operation==='latest_run')return run;
  if(operation==='events'){
    cursors.push(args.after);
    if(eventCount++===0)return {items:[{run_id:run.id,sequence:1,kind:'model.partial',data:{message:'Partial response only'},created_at:'2026-10-24T12:00:01Z'}],next_cursor:'run_demo:1',has_more:false};
    return {items:[],next_cursor:args.after,has_more:false};
  }
  throw Error('Unexpected operation');
});
try {
  const w=dom.window;
  await until(()=>w.document.body.textContent.includes('Connected to your local workspace.'));
  button(w,'New task').click();await wait(60);
  fill(w,'task-title',created.title);fill(w,'task-instruction',created.instruction);await wait(50);
  const form=w.document.querySelector('form');
  form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await until(()=>button(w,'Retry same task'));
  assert.equal(submissions.length,1);
  assert.equal(w.document.getElementById('task-instruction').value,created.instruction);
  assert.equal(w.document.getElementById('task-title').readOnly,true);
  const retained=JSON.parse(w.localStorage.getItem('veya-task-draft-v1'));
  assert.equal(retained.client_request_id,submissions[0].client_request_id);
  button(w,'Retry same task').click();
  await until(()=>w.document.body.textContent.includes('Partial response only'));
  assert.equal(submissions.length,2);assert.deepEqual(submissions[0],submissions[1]);
  assert.equal(w.document.querySelectorAll('.work-events li').length,1);
  assert.ok(w.document.body.textContent.includes('Saved and queued. AI execution is not connected yet.'));
  assert.equal(w.document.activeElement.id,'activity-title');
  await until(()=>cursors.includes('run_demo:1'));
  assert.equal(w.document.querySelectorAll('.work-events li').length,1);
  assert.equal(w.document.querySelector('.work-activity script'),null);
  w.document.querySelector('[aria-label="Close task details"]').click();await wait(60);
  button(w,'New task').click();await wait(60);
  assert.equal(w.document.activeElement.id,'task-title');
  assert.equal(w.document.getElementById('task-title').value,'');
} finally {dom.window.close();}
const browser=boot();
try {await until(()=>button(browser.window,'New task'));button(browser.window,'New task').click();await wait(60);assert.equal(button(browser.window,'Save task').disabled,true);assert.ok(browser.window.document.body.textContent.includes('Browser preview.'));}
finally {browser.window.close();}
let rejected = false;
const invalid=boot(async(command,{operation,args}={})=>{
  if(command==='runtime_health')return {state:'ready',message:'Connected'};
  if(operation==='recovery')return {required:false};
  if(operation==='list_tasks')return {items:[],next_cursor:null};
  if(operation==='submit_task') { rejected=true;throw 'invalid_input'; }
  throw Error('Unexpected operation');
});
try {
  const w=invalid.window;
  await until(()=>w.document.body.textContent.includes('Connected'));
  button(w,'New task').click();await wait(60);
  fill(w,'task-title','Invalid request fixture');fill(w,'task-instruction','Preserve editable text');await wait(50);
  button(w,'Save task').click();
  await until(()=>rejected && w.document.querySelector('[role="alert"]'));
  assert.equal(w.document.getElementById('task-title').readOnly,false);
  assert.equal(w.document.getElementById('task-instruction').value,'Preserve editable text');
  fill(w,'task-title','Corrected title');await wait(50);
  assert.equal(JSON.parse(w.localStorage.getItem('veya-task-draft-v1')).title,'Corrected title');
} finally {invalid.window.close();}
const tasks=[created,{...created,id:'task_waiting',title:'Check supplier quantity',instruction:'Investigate missing delivery',state:'waiting'},{...created,id:'task_done',title:'Review completed',instruction:'Verified fixture only',state:'succeeded'}];
const listing=boot(async(command,{operation,args}={})=>{
  if(command==='runtime_health')return {state:'ready',message:'Connected'};
  if(operation==='recovery')return {required:true};
  if(operation==='list_tasks')return {items:tasks,next_cursor:null};
  if(operation==='latest_run')return {id:'run_waiting',state:'running'};
  if(operation==='events')return {items:[],next_cursor:args.after,has_more:false};
  throw Error('Unexpected operation');
});
try {
  const w=listing.window;
  await until(()=>w.document.querySelectorAll('.work-table tbody tr').length===3);
  const filter=label=>[...w.document.querySelectorAll('.work-filters button')].find(b=>b.textContent.startsWith(label));
  filter('Needs attention').click();await wait(60);
  assert.equal(w.document.querySelectorAll('.work-table tbody tr').length,1);
  const open=w.document.querySelector('.work-task-link');open.focus();open.click();
  await until(()=>w.document.querySelector('dialog[open] #activity-title'));
  await until(()=>w.document.querySelector('.work-detail-heading').textContent.includes('In progress'));
  assert.ok(w.document.querySelector('#task-panel-activity').hidden);
  w.document.getElementById('task-tab-overview').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
  await wait(50);assert.equal(w.document.getElementById('task-tab-activity').getAttribute('aria-selected'),'true');
  const panel=w.document.querySelector('dialog[open]');panel.dispatchEvent(new w.Event('cancel',{cancelable:true}));await wait(50);
  assert.equal(w.document.querySelector('dialog[open]'),null);
  assert.ok(w.document.body.textContent.includes('No matching work'),'live state change updates the filtered list');
  button(w,'Clear filters').click();await wait(50);
  const search=w.document.querySelector('input[type="search"]');
  Object.getOwnPropertyDescriptor(w.HTMLInputElement.prototype,'value').set.call(search,'missing delivery');search.dispatchEvent(new w.Event('input',{bubbles:true}));await wait(50);
  assert.equal(w.document.querySelectorAll('.work-table tbody tr').length,1);
  w.document.querySelector('[aria-label="Expand navigation"]').click();await wait(50);
  assert.equal(w.localStorage.getItem('veya-navigation-v1'),'expanded');
  button(w,'New task').click();await wait(50);fill(w,'task-title','Read-only draft');fill(w,'task-instruction','Should not submit');await wait(50);
  assert.equal(button(w,'Save task').disabled,true);
  w.document.querySelector('[aria-label="Close new task"]').click();await wait(50);button(w,'New task').click();await wait(50);
  assert.equal(w.document.getElementById('task-title').value,'Read-only draft');
} finally {listing.window.close();}
let reconnectState='ready', recoveryCalls=0, releaseRecovery, reconnectSubmissions=0;
const reconnect=boot(async(command,{operation}={})=>{
  if(command==='runtime_health')return {state:reconnectState,message:reconnectState==='ready'?'Connected':'Connection interrupted'};
  if(operation==='recovery')return ++recoveryCalls===1?{required:false}:await new Promise(resolve=>{releaseRecovery=resolve;});
  if(operation==='list_tasks')return {items:[],next_cursor:null};
  if(operation==='submit_task'){reconnectSubmissions++;throw Error('Unexpected submission');}
  throw Error('Unexpected operation');
});
try {
  const w=reconnect.window;
  await until(()=>recoveryCalls===1);
  button(w,'New task').click();await wait(50);
  fill(w,'task-title','Preserve on reconnect');fill(w,'task-instruction','Wait for recovery review');
  await until(()=>!button(w,'Save task').disabled);
  reconnectState='failed';await until(()=>button(w,'Save task').disabled);
  reconnectState='ready';await until(()=>releaseRecovery);await wait(50);
  assert.equal(button(w,'Save task').disabled,true,'recovery pending after reconnect must keep submission locked');
  w.document.querySelector('form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await wait(50);
  assert.equal(reconnectSubmissions,0);
  releaseRecovery({required:true});await wait(60);
  assert.equal(button(w,'Save task').disabled,true);
  assert.equal(w.document.getElementById('task-title').value,'Preserve on reconnect');
} finally {reconnect.window.close();}
console.log('PASS: workspace IPC integration; duplicate guard, ambiguous retry identity, drafts, escaping, focus, cursor resume, no false completion, browser/read-only states, reconnect recovery gating, search, status filters, live list update, tabs and navigation persistence.');
