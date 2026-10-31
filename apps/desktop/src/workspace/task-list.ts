import {QueueQuery} from '../features/work/work-queue';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Task } from './client';
import { WorkWelcome } from '../features/work/work-welcome';
export const stateLabel: Record<string, string> = {
  queued: 'Queued',
  running: 'In progress',
  waiting: 'Waiting',
  succeeded: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};
const filters = [
  {id:'all',label:'All work'}, {id:'active',label:'Active'},
  {id:'attention',label:'Needs attention'}, {id:'completed',label:'Completed'},
];
@Component({
  selector: 'veya-task-list',
  imports: [WorkWelcome],
  template: ` <section class="work-list" aria-label="Recent work" [attr.aria-busy]="loading">
    <div class="work-filters" role="group" aria-label="Filter work">
      @for (item of filters; track item.id) {
        <button
          type="button"
          [attr.aria-pressed]="query.status === item.id"
          (click)="change({status:item.id})"
        >
          {{ item.label }}
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
          [value]="query.search"
          (input)="change({search:search.value})"
          maxlength="200"
      /></label>
      <label class="work-sort">Sort
        <select #sort [value]="query.sort" (change)="change({sort:sort.value === 'oldest' ? 'oldest' : 'newest'})">
          <option value="newest">Newest first</option><option value="oldest">Oldest first</option>
        </select>
      </label>
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
            Saved tasks, {{query.sort === 'oldest' ? 'oldest' : 'newest'}} first
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
    } @else if (!error) {
      <div class="work-empty" role="status">
        @if (!hasFilter() && !hasPrevious) { <veya-work-welcome /> }
        <h2>{{ hasFilter() ? 'No matching work' : 'Your work starts here' }}</h2>
        <p>
          {{
            hasFilter()
              ? 'Try a different search or view.'
              : 'Give a task a clear brief. Keep its instructions and progress together, from the first note onward.'
          }}
        </p>
        @if (hasFilter()) {
          <button class="work-secondary" (click)="change({search:'',status:'all'}); search.focus()">
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
        }}</span
      ><div class="work-pagination"><button class="work-secondary" [disabled]="!hasPrevious || loading" (click)="page.emit('previous')">Previous</button><button class="work-secondary" [disabled]="!hasNext || loading" (click)="page.emit('next')">Next</button></div><span>Saved on this device</span>
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
  @Input() query: QueueQuery = {search:'',status:'all',sort:'newest'};
  @Input() hasPrevious = false;
  @Input() hasNext = false;
  @Output() queryChange = new EventEmitter<QueueQuery>();
  @Output() page = new EventEmitter<'next' | 'previous'>();
  change(value: Partial<QueueQuery>) {this.queryChange.emit({...this.query,...value});}
  readonly filters = filters;
  readonly labels = stateLabel;
  visible() { return this.tasks; }
  hasFilter() {
    return this.tasks.length > 0 || Boolean(this.query.search.trim()) || this.query.status !== 'all';
  }
  date(value: string) {
    const d = new Date(value);
    return Number.isNaN(d.getTime())
      ? 'Date unavailable'
      : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }
}
