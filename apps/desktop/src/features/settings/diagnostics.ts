import { Component, Input, OnChanges, OnDestroy, signal } from '@angular/core';
import { call } from '../../workspace/client';
import type { DiagnosticBundle } from '../../../../../packages/contracts/src/index';

type Bundle = DiagnosticBundle;

export async function loadDiagnostics(): Promise<Bundle> {
  const value = await call('export_diagnostics') as Bundle;
  if (!value || value.format_version !== 1 || typeof value.content !== 'string' || value.content.length > 262144 || !/^[a-f0-9]{64}$/.test(value.sha256) || !Number.isInteger(value.records) || value.records < 0 || value.records > 100 || typeof value.truncated !== 'boolean' || typeof value.generated_at !== 'string' || typeof value.runtime_version !== 'string') throw new Error('invalid_response');
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value.content));
  const hex = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
  if (hex !== value.sha256) throw new Error('invalid_response');
  return value;
}

@Component({
  selector: 'veya-diagnostics',
  template: `<section class="work-diagnostics" aria-labelledby="diagnostics-heading">
    <h3 id="diagnostics-heading">Diagnostics</h3>
    <p class="work-muted">Prepare a local report to investigate a problem. It includes recent operation IDs, timing and health counters. Document text, prompts and credentials are excluded.</p>
    <button class="work-secondary" [disabled]="disabled || pending()" (click)="prepare()">{{pending() ? 'Preparing…' : 'Prepare diagnostic report'}}</button>
    @if(disabled) { <p class="work-muted">Reconnect to prepare a fresh report.</p> }
    @if(error()) { <p role="alert">{{error()}}</p> }
    @if(bundle(); as report) {
      <div class="work-diagnostic-result" role="status">
        <strong>{{report.records}} recent operations · ready to save</strong>
        <p class="work-muted">{{report.truncated ? 'Older records are omitted from this bounded report.' : 'All currently retained records are included.'}}</p>
        <button class="work-primary" (click)="save()">Save diagnostic report</button>
      </div>
    }
  </section>`,
})
export class Diagnostics implements OnChanges, OnDestroy {
  @Input() disabled = false;
  readonly pending = signal(false);
  readonly error = signal('');
  readonly bundle = signal<Bundle | null>(null);
  private version = 0;
  ngOnChanges() { this.version++; this.pending.set(false); }
  ngOnDestroy() { this.version++; }
  async prepare() {
    if (this.disabled || this.pending()) return;
    const version = ++this.version;
    this.pending.set(true); this.error.set('');
    try { const report = await loadDiagnostics(); if (version === this.version) this.bundle.set(report); }
    catch { if (version === this.version) this.error.set('The report could not be prepared. Reconnect and try again.'); }
    finally { if (version === this.version) this.pending.set(false); }
  }
  save() {
    const report = this.bundle(); if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'veya-diagnostics.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
