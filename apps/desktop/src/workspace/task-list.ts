import { Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { Task } from './client';
export const stateLabel: Record<string, string> = {
  queued: 'Queued',
  running: 'In progress',
  waiting: 'Waiting',
  succeeded: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};
const filters = [
  { id: 'all', label: 'All work', matches: (_task: Task) => true },
  {
    id: 'active',
    label: 'Active',
    matches: (task: Task) => ['queued', 'running'].includes(task.state),
  },
  {
    id: 'attention',
    label: 'Needs attention',
    matches: (task: Task) => ['waiting', 'failed'].includes(task.state),
  },
  { id: 'completed', label: 'Completed', matches: (task: Task) => task.state === 'succeeded' },
];
@Component({
  selector: 'veya-task-list',
  template: ` <section class="work-list" aria-label="Recent work" [attr.aria-busy]="loading">
    <div class="work-filters" role="group" aria-label="Filter work">
      @for (item of filters; track item.id) {
        <button
          type="button"
          [attr.aria-pressed]="filter() === item.id"
          (click)="filter.set(item.id)"
        >
          {{ item.label }}<span>{{ count(item.id) }}</span>
        </button>
      }
    </div>
    <div class="work-list-tools">
      <label class="work-search"
        ><i class="ph ph-magnifying-glass" aria-hidden="true"></i
        ><span class="work-sr-only">Search recent work</span>
        <input
          #search
          type="search"
          autocomplete="off"
          placeholder="Search recent work…"
          [value]="query()"
          (input)="query.set(search.value)"
      /></label>
      <button
        type="button"
        class="work-secondary"
        (click)="refresh.emit()"
        [disabled]="!connected || loading"
      >
        <i class="ph ph-arrow-clockwise" aria-hidden="true"></i
        >{{ loading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>
    @if (error) {
      <p class="work-error" role="alert">{{ error }} Refresh to try again.</p>
    }
    @if (loading && tasks.length === 0) {
      <p class="work-empty" role="status">Loading saved work…</p>
    } @else if (visible().length) {
      <div class="work-table-wrap">
        <table class="work-table">
          <caption class="work-sr-only">
            Saved tasks, newest first
          </caption>
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col">Status</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            @for (task of visible(); track task.id) {
              <tr>
                <td>
                  <button
                    class="work-task-link"
                    (click)="selected.emit(task)"
                    [attr.aria-label]="'Open task: ' + task.title"
                  >
                    <span>{{ task.title }}</span
                    ><small>{{ task.instruction }}</small>
                  </button>
                </td>
                <td>
                  <span class="work-task-state" [attr.data-state]="task.state">{{
                    labels[task.state]
                  }}</span>
                </td>
                <td>
                  <time [attr.datetime]="task.created_at">{{ date(task.created_at) }}</time>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else {
      <div class="work-empty" role="status">
        <h2>{{ hasFilter() ? 'No matching work' : 'Your work starts here' }}</h2>
        <p>
          {{
            hasFilter()
              ? 'Try a different search or view.'
              : 'Give a task a clear brief. Keep its instructions and progress together, from the first note onward.'
          }}
        </p>
        @if (hasFilter()) {
          <button class="work-secondary" (click)="query.set(''); filter.set('all'); search.focus()">
            Clear filters
          </button>
        } @else {
          <button class="work-secondary" (click)="newTask.emit()">Create your first task</button>
        }
      </div>
    }
    <footer class="work-list-footer">
      <span aria-live="polite"
        >{{ visible().length }} {{ visible().length === 1 ? 'task' : 'tasks'
        }}{{ tasks.length === 10 ? ' · Latest 10 saved tasks' : '' }}</span
      ><span>Saved on this device</span>
    </footer>
  </section>`,
})
export class TaskList {
  @Input() tasks: Task[] = [];
  @Input() loading = false;
  @Input() connected = false;
  @Input() error = '';
  @Output() refresh = new EventEmitter<void>();
  @Output() selected = new EventEmitter<Task>();
  @Output() newTask = new EventEmitter<void>();
  readonly filter = signal('all');
  readonly query = signal('');
  readonly filters = filters;
  readonly labels = stateLabel;
  count(id: string) {
    return this.tasks.filter(filters.find((f) => f.id === id)!.matches).length;
  }
  visible() {
    const f = filters.find((f) => f.id === this.filter()) ?? filters[0];
    const q = this.query().trim().toLocaleLowerCase();
    return this.tasks.filter(
      (t) => f.matches(t) && `${t.title} ${t.instruction}`.toLocaleLowerCase().includes(q),
    );
  }
  hasFilter() {
    return this.tasks.length > 0 || Boolean(this.query().trim()) || this.filter() !== 'all';
  }
  date(value: string) {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? 'Date unavailable'
      : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
