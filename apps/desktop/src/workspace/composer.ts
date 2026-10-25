import { Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { Draft, errorText, submit, Task } from './client';

const KEY = 'veya-task-draft-v1';
function empty(): Draft {
  return { client_request_id: crypto.randomUUID(), title: '', instruction: '', attempted: false };
}
function readDraft(): Draft {
  try {
    const v: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (
      v &&
      typeof v === 'object' &&
      'client_request_id' in v &&
      'title' in v &&
      'instruction' in v &&
      'attempted' in v &&
      typeof v.client_request_id === 'string' &&
      /^[a-zA-Z0-9_-]{1,64}$/.test(v.client_request_id) &&
      typeof v.title === 'string' &&
      typeof v.instruction === 'string' &&
      typeof v.attempted === 'boolean'
    )
      return v as Draft;
  } catch {
    /* Corrupt drafts are never submitted. */
  }
  return empty();
}

@Component({
  selector: 'veya-composer',
  template: ` <form class="work-composer" (submit)="send($event)" [attr.aria-busy]="pending()">
    <label for="task-title">Task name</label>
    <input
      id="task-title"
      name="title"
      autocomplete="off"
      data-autofocus
      maxlength="200"
      required
      [value]="draft().title"
      [readOnly]="draft().attempted"
      (input)="edit('title', $event)"
      placeholder="For example, review the supplier order"
    />
    <label for="task-instruction">What would you like done?</label>
    <textarea
      id="task-instruction"
      name="instruction"
      autocomplete="off"
      maxlength="20000"
      required
      rows="8"
      [value]="draft().instruction"
      [readOnly]="draft().attempted"
      (input)="edit('instruction', $event)"
      placeholder="Describe the task and what a useful result should include."
    ></textarea>
    <div class="work-submit">
      <p>Tasks are saved locally. AI execution and attachments are coming next.</p>
      <button
        class="work-primary"
        [disabled]="!enabled || pending() || !draft().title.trim() || !draft().instruction.trim()"
      >
        {{ pending() ? 'Saving task…' : draft().attempted ? 'Retry same task' : 'Save task' }}
      </button>
    </div>
    @if (draft().attempted && !pending()) {
      <p class="work-muted">
        We could not confirm whether this task was saved. Retry checks the same submission. Your
        original brief is kept intact to avoid duplicates.
      </p>
    }
    @if (error()) {
      <p class="work-error" role="alert">{{ error() }}</p>
    }
  </form>`,
})
export class Composer {
  @Input() enabled = false;
  @Output() created = new EventEmitter<Task>();
  readonly draft = signal(readDraft());
  readonly pending = signal(false);
  readonly error = signal('');
  private save(next: Draft) {
    this.draft.set(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
      return true;
    } catch {
      this.error.set(
        'Your draft could not be saved on this device. Free storage or allow local storage before submitting.',
      );
      return false;
    }
  }
  edit(key: 'title' | 'instruction', event: Event) {
    if (!this.draft().attempted)
      this.save({ ...this.draft(), [key]: (event.target as HTMLInputElement).value });
  }
  async send(event: Event) {
    event.preventDefault();
    const draft = this.draft();
    if (!this.enabled || this.pending() || !draft.title.trim() || !draft.instruction.trim()) return;
    const request = {
      ...draft,
      title: draft.title.trim(),
      instruction: draft.instruction.trim(),
      attempted: true,
    };
    if (!this.save(request)) return;
    this.pending.set(true);
    this.error.set('');
    try {
      const result = await submit(request);
      this.save(empty());
      this.created.emit(result.task);
    } catch (cause) {
      if ((cause instanceof Error ? cause.message : String(cause)) === 'invalid_input')
        this.save({ ...request, attempted: false });
      this.error.set(errorText(cause));
    } finally {
      this.pending.set(false);
    }
  }
}
