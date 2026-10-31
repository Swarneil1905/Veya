import { Component, Input, OnChanges, OnDestroy, signal } from '@angular/core';
import { call } from '../../workspace/client';
import { documentError, object } from './client';

type Evidence = { value: string; citation: string; locator: string; confidence: number | null; region: number[] | null };
type Field = { name: string; original: string | null; value: string; reason: string; evidence: Evidence[]; reviewer?: string };
type Review = { revision: number; reviewed: boolean; fields: Field[] };
const names = ['vendor', 'invoice_number', 'total', 'currency'];
function decode(value: unknown): Review {
  const result = object(value);
  if (!Number.isInteger(result['revision']) || typeof result['reviewed'] !== 'boolean' || !Array.isArray(result['fields'])) throw new Error('invalid_response');
  const fields = result['fields'].map(raw => {
    const field = object(raw);
    if (!names.includes(String(field['name'])) || typeof field['value'] !== 'string' || !Array.isArray(field['evidence']) || !(field['original'] === null || typeof field['original'] === 'string')) throw new Error('invalid_response');
    return field as Field;
  });
  if (fields.length !== 4 || new Set(fields.map(f => f.name)).size !== 4) throw new Error('invalid_response');
  return { revision: Number(result['revision']), reviewed: result['reviewed'], fields };
}
@Component({
  selector: 'veya-field-review',
  template: `
    <section class="field-review" aria-labelledby="field-review-title">
      <h3 id="field-review-title">Invoice fields</h3>
      <p class="work-muted">Verify these values against the source. Saving records your corrections; it does not approve a payment.</p>
      @if (loading()) { <p role="status">Loading field evidence…</p> }
      @if (error()) { <p role="alert" class="work-error">{{ error() }}</p><button class="work-secondary" type="button" (click)="load()">Reload fields</button> }
      @if (review(); as item) {
        <form (submit)="save($event)">
          @for (field of item.fields; track field.name) {
            <div class="field-row">
              <label [for]="'invoice-' + field.name">{{ label(field.name) }}</label>
              <input [id]="'invoice-' + field.name" [name]="field.name" required [maxLength]="field.name === 'currency' ? 3 : 100" [value]="values()[field.name]" [disabled]="saving()" (input)="edit(field.name, $event)" />
              <p class="work-muted">Original: {{ field.original ?? 'Not resolved' }} · {{ field.reason.replaceAll('_', ' ') }}</p>
              @for (source of field.evidence; track $index) {
                <p class="field-evidence">{{ source.locator }} — {{ source.value }}
                  @if (source.confidence !== null) { <span> · {{ percent(source.confidence) }}% OCR confidence</span> }
                  @if (source.region) { <span> · Region {{ source.region.join(', ') }}</span> }
                </p>
              }
            </div>
          }
          <label for="invoice-review-note">Verification note</label>
          <textarea id="invoice-review-note" required maxlength="2000" [disabled]="saving()" [value]="note()" (input)="note.set(text($event))" placeholder="Explain corrections and how missing or conflicting values were resolved"></textarea>
          <button type="submit" class="work-primary" [disabled]="saving()">{{ saving() ? 'Saving…' : 'Save reviewed fields' }}</button>
          @if (saved()) { <p role="status">Review saved. Original values and source evidence are retained.</p> }
        </form>
      }
    </section>`,
  styles: [`:host{display:block}.field-review{border-top:1px solid var(--work-border,#d9dfda);margin-top:24px;padding-top:12px}.field-row{margin:18px 0}label{display:block;font-weight:600;margin-bottom:6px}input,textarea{box-sizing:border-box;width:100%;font:inherit;color:inherit;background:var(--work-surface,#fff);border:1px solid var(--work-border,#9ca89f);border-radius:6px;padding:9px}textarea{min-height:84px;margin-bottom:12px}.field-evidence{font-size:12px;overflow-wrap:anywhere}.work-muted{font-size:13px}input:focus-visible,textarea:focus-visible{outline:2px solid #216744;outline-offset:2px}`],
})
export class FieldReview implements OnChanges, OnDestroy {
  @Input({required: true}) documentId = '';
  readonly review = signal<Review | null>(null);
  readonly values = signal<Record<string,string>>({});
  readonly note = signal(''); readonly loading = signal(false); readonly saving = signal(false);
  readonly saved = signal(false); readonly error = signal('');
  private generation = 0;
  ngOnChanges() { void this.load(); }
  ngOnDestroy() { this.generation++; }
  text(event: Event) { return (event.target as HTMLInputElement).value; }
  edit(name: string, event: Event) { this.values.update(v => ({...v, [name]: this.text(event)})); this.saved.set(false); }
  label(name: string) { return ({vendor:'Vendor', invoice_number:'Invoice number', total:'Total amount', currency:'Currency'} as Record<string,string>)[name]; }
  percent(value: number) { return Math.round(value * 100); }
  async load() {
    const generation = ++this.generation; this.loading.set(true); this.error.set(''); this.review.set(null); this.saved.set(false); this.note.set('');
    try { const value = decode(await call('document_fields', {id:this.documentId})); if (generation !== this.generation) return; this.review.set(value); this.values.set(Object.fromEntries(value.fields.map(f => [f.name,f.value]))); }
    catch (error) { if (generation === this.generation) this.error.set(documentError(error)); }
    finally { if (generation === this.generation) this.loading.set(false); }
  }
  async save(event: Event) {
    event.preventDefault(); const review = this.review(); if (!review || this.saving()) return;
    const generation = this.generation; this.saving.set(true); this.error.set('');
    try { const value = decode(await call('review_document_fields', {id:this.documentId, revision:review.revision, values:this.values(), note:this.note()})); if (generation !== this.generation) return; this.review.set(value); this.saved.set(true); }
    catch (error) { if (generation === this.generation) this.error.set(error instanceof Error && error.message === 'conflict' ? 'Another review was saved. Your edits remain here; reload to compare before saving again.' : 'Fields could not be saved. Check every value and retry.'); }
    finally { if (generation === this.generation) this.saving.set(false); }
  }
}
