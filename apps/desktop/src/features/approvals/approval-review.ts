import { Component, Input, OnInit, OnDestroy, OnChanges, SimpleChanges, signal } from '@angular/core';
import { JsonPipe } from '@angular/common';
import type { ReviewDetail, ReviewSummary } from '../../../../../packages/contracts/src/index';
import { call, errorText } from '../../workspace/client';
import { Panel } from '../../workspace/panel';
import { reviewTiming } from './aging';
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_response');
  return value as Record<string,unknown>;
}
function summary(value: unknown): ReviewSummary {
  const v = record(value);
  for (const key of ['id','proposal_id','operation_key','policy_version','state','attention']) if (typeof v[key] !== 'string') throw new Error('invalid_response');
  if (!Number.isSafeInteger(v['revision']) || Number(v['revision'])<1 || typeof v['expires_at'] !== 'number' || !Number.isFinite(v['expires_at']) || typeof v['expired'] !== 'boolean') throw new Error('invalid_response');
  if (!['pending','approved','rejected','superseded'].includes(String(v['state']))) throw new Error('invalid_response');
  return v as ReviewSummary;
}
function detail(value: unknown): ReviewDetail {
  const v = record(value); summary(value);
  for (const key of ['tool_name','tool_version','arguments_hash','run_id','context_hash','policy_reason']) if (typeof v[key] !== 'string') throw new Error('invalid_response');
  record(v['arguments']); const scope = record(v['scope']);
  for (const key of ['tenant_id','workspace_id','actor_id']) if (typeof scope[key] !== 'string') throw new Error('invalid_response');
  return v as ReviewDetail;
}
@Component({selector:'veya-approvals',imports:[Panel,JsonPipe],template:`
<section aria-label="Approval inbox" [attr.aria-busy]="loading()">
  <div class="work-list-tools"><p class="work-muted">Review the exact change before authorizing it.</p><button class="work-secondary" [disabled]="!connected || loading()" (click)="load()">Refresh reviews</button></div>
  @if(error()){<p role="alert" class="work-error">{{error()}}</p>}
  @if(loading() && !items().length){<p class="work-empty" role="status">Loading reviews…</p>}
  @else if(!items().length){<div class="work-empty"><h2>No decisions waiting</h2><p>Requests appear here when a configured workflow needs your approval.</p></div>}
  @else {<ul class="review-list">@for(item of items();track item.id){<li><button class="review-row" (click)="open(item.id)"><span><strong>Review operation</strong><small>{{item.operation_key}}</small></span><span>{{timing(item.expires_at, now())}}</span><i class="ph ph-caret-right" aria-hidden="true"></i></button></li>}</ul>}
  @if(next() !== null){<button class="work-secondary" [disabled]="loading()" (click)="load(true)">More reviews</button>}
</section>
@if(selected();as item){<veya-panel title="Review operation" (closed)="close()"><div class="work-panel-content review-content">
  <h2 data-autofocus tabindex="-1">{{item.tool_name}}</h2><p>{{item.policy_reason}}</p>
  <dl class="work-properties"><div><dt>Workspace</dt><dd>{{item.scope['workspace_id']}}</dd></div><div><dt>Reviewer</dt><dd>{{item.scope['actor_id']}}</dd></div><div><dt>Policy</dt><dd>{{item.policy_version}}</dd></div><div><dt>Status</dt><dd>{{item.state}}</dd></div><div><dt>Review deadline</dt><dd>{{timing(item.expires_at,now())}}</dd></div></dl>
  <h3>Exact arguments</h3><pre class="review-arguments">{{item.arguments | json}}</pre>
  <details><summary>Evidence and operation identity</summary><dl class="work-properties"><div><dt>Run</dt><dd>{{item.run_id}}</dd></div><div><dt>Proposal</dt><dd>{{item.proposal_id}}</dd></div><div><dt>Arguments digest</dt><dd>{{item.arguments_hash}}</dd></div><div><dt>Authorization context</dt><dd>{{item.context_hash}}</dd></div></dl></details>
  @if(decisionError()){<p class="work-error" role="alert">{{decisionError()}} <button class="work-link" (click)="open(item.id)">Refresh this review</button></p>}
  @if(item.state==='pending') {<label class="review-note" for="review-note">Decision note<textarea id="review-note" #noteInput rows="3" maxlength="2000" [value]="note()" (input)="note.set(noteInput.value)" placeholder="Explain your decision"></textarea></label>
  <p class="work-muted">Approval authorizes only this operation. It does not execute it.</p>
  <div class="review-actions"><button class="work-secondary" [disabled]="!canDecide()" (click)="decide('reject')">Reject operation</button><button class="work-primary" [disabled]="!canDecide()" (click)="decide('approve')">{{saving()?'Saving decision…':'Approve operation'}}</button></div>}
  @else {<p role="status" class="work-notice">{{item.state==='approved'?'Approval recorded.':item.state==='rejected'?'Rejection recorded.':'This request is no longer current. Request a fresh review.'}}</p>}
</div></veya-panel>}
`})
export class ApprovalReview implements OnInit,OnDestroy,OnChanges {
  @Input() connected=false;
  @Input() readOnly=true;
  readonly items=signal<ReviewSummary[]>([]);
  readonly selected=signal<ReviewDetail|null>(null);
  readonly next=signal<number|null>(null);
  readonly loading=signal(false); readonly saving=signal(false);
  readonly error=signal(''); readonly decisionError=signal(''); readonly note=signal('');
  readonly now=signal(Date.now()); readonly timing=reviewTiming;
  private timer: ReturnType<typeof setInterval>|undefined;
  private version=0; private detailVersion=0; private closed=false;
  close(){this.detailVersion++;this.selected.set(null);this.note.set('');this.decisionError.set('');}
  ngOnChanges(changes:SimpleChanges){if(changes['connected'] && !changes['connected'].firstChange && this.connected)void this.load();}
  ngOnInit(){void this.load();this.timer=setInterval(()=>this.now.set(Date.now()),1000);}
  ngOnDestroy(){this.closed=true;this.version++;this.detailVersion++;clearInterval(this.timer);}
  async load(more=false){
    if(!this.connected)return;
    const version=++this.version;this.loading.set(true);
    try {const value=record(await call('list_approvals',{after:more?this.next():null}));
      if(!Array.isArray(value['items']) || !(value['next_cursor']===null || Number.isSafeInteger(value['next_cursor'])))throw new Error('invalid_response');
      const items=value['items'].map(summary);if(version!==this.version)return;
      this.items.set(more?[...this.items(),...items]:items);this.next.set(value['next_cursor'] as number|null);this.error.set('');
    }catch(cause){if(version===this.version)this.error.set(errorText(cause));}
    finally{if(version===this.version)this.loading.set(false);}
  }
  async open(id:string){const version=++this.detailVersion;this.note.set('');try {const item=detail(await call('get_approval',{id}));if(!this.closed && version===this.detailVersion){this.selected.set(item);this.decisionError.set('');}}
    catch(cause){if(!this.closed && version===this.detailVersion)this.error.set(errorText(cause));}}
  canDecide(){const item=this.selected();return this.connected && !this.readOnly && !this.saving() && !!this.note().trim() && item?.state==='pending' && !item.expired && item.expires_at*1000>this.now();}
  async decide(decision:'approve'|'reject'){
    const item=this.selected();if(!item || !this.canDecide())return;this.saving.set(true);const version=this.detailVersion;
    try{const result=detail(await call('decide_approval',{id:item.id,revision:item.revision,decision,note:this.note().trim()}));if(!this.closed){if(version===this.detailVersion)this.selected.set(result);void this.load();}}
    catch(cause){if(!this.closed && version===this.detailVersion)this.decisionError.set(cause instanceof Error && cause.message==='conflict'?'This request changed or expired. Refresh it before deciding.':errorText(cause));}
    finally{this.saving.set(false);}
  }
}
