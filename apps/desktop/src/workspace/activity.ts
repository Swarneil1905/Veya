import { ExecutionControls } from "../features/work/execution-controls";
import {
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  signal,
} from "@angular/core";
import { ActivityEvent, errorText, events, latestRun, Task } from "./client";
import { ResultPanel } from "../features/results/result-panel";
import { TaskDocuments } from "../features/documents/task-documents";
import { stateLabel } from "./task-list";

@Component({
  selector: "veya-activity",
  imports: [ResultPanel, TaskDocuments, ExecutionControls],
  template: ` <section class="work-activity" aria-labelledby="activity-title">
    <div class="work-detail-heading">
      <span class="work-task-state" [attr.data-state]="status()">{{
        labels[status()]
      }}</span>
      <h2 id="activity-title" data-autofocus tabindex="-1">{{ task.title }}</h2>
    </div>
    <div class="work-detail-tabs" role="tablist" aria-label="Task information">
      @for (item of tabs; track item) {
        <button
          [id]="'task-tab-' + item"
          role="tab"
          [attr.aria-selected]="tab() === item"
          [attr.aria-controls]="'task-panel-' + item"
          [tabIndex]="tab() === item ? 0 : -1"
          (click)="tab.set(item)"
          (keydown)="moveTab($event)"
        >
          {{
            item === "overview"
              ? "Overview"
              : item === "activity"
                ? "Activity"
                : "Results"
          }}
        </button>
      }
    </div>
    <div class="work-panel-content">
      <veya-execution-controls
        [runId]="runId()"
        [state]="status()"
        [disabled]="readOnly || !connected"
      />
      @if (!connected) {
        <p role="status">
          Disconnected. Saved activity will resume when the runtime reconnects.
        </p>
      }
      @if (error()) {
        <p class="work-error" role="alert">
          {{ error() }} Activity will reconnect automatically.
        </p>
      }
      <div
        id="task-panel-overview"
        role="tabpanel"
        aria-labelledby="task-tab-overview"
        [hidden]="tab() !== 'overview'"
        tabindex="0"
      >
        <h3>Brief</h3>
        <p class="work-instruction">{{ task.instruction }}</p>
        <dl class="work-properties">
          <div>
            <dt>Created</dt>
            <dd>
              <time [attr.datetime]="task.created_at">{{
                date(task.created_at)
              }}</time>
            </dd>
          </div>
          <div>
            <dt>Workspace</dt>
            <dd>Personal</dd>
          </div>
        </dl>
        <veya-task-documents
          [taskId]="task.id"
          [readOnly]="readOnly || !connected"
        />
        <div class="work-detail-note">
          <h3>What happens next</h3>
          <p>
            Your brief is saved. Start read-only work using a tested model
            connection. Recorded progress appears in Activity, and source-backed
            output appears in Results.
          </p>
        </div>
      </div>
      <div
        id="task-panel-activity"
        role="tabpanel"
        aria-labelledby="task-tab-activity"
        [hidden]="tab() !== 'activity'"
        tabindex="0"
      >
        <h3>Recorded activity</h3>
        @if (loading()) {
          <p role="status">Loading activity…</p>
        }
        @if (!loading() && rows().length === 0) {
          <p class="work-muted">No execution activity has been recorded.</p>
        }
        <ol class="work-events" aria-label="Recorded activity">
          @for (row of rows(); track row.run_id + ":" + row.sequence) {
            <li>
              <span class="work-event-marker" aria-hidden="true"></span>
              <div>
                <span>{{ eventText(row) }}</span
                ><time [attr.datetime]="row.created_at">{{
                  date(row.created_at)
                }}</time>
              </div>
            </li>
          }
        </ol>
        @if (rows().length === 500) {
          <p>
            Showing the latest 500 events. The complete history remains saved.
          </p>
        }
        <p class="work-muted">Partial activity is not a completed result.</p>
      </div>
      @if (tab() === "results") {
        <div
          id="task-panel-results"
          role="tabpanel"
          aria-labelledby="task-tab-results"
          tabindex="0"
        >
          <veya-results [runId]="runId()" [runState]="status()" />
        </div>
      }
    </div>
  </section>`,
})
export class Activity implements OnChanges, OnDestroy {
  @Input({ required: true }) task!: Task;
  @Input() connected = false;
  @Input() readOnly = true;
  readonly runId = signal("");
  @Input() initialTab: "overview" | "activity" = "overview";
  @Output() stateChange = new EventEmitter<{ id: string; state: string }>();
  readonly tabs = ["overview", "activity", "results"] as const;
  readonly labels = stateLabel;
  readonly tab = signal<"overview" | "activity" | "results">("overview");
  readonly rows = signal<ActivityEvent[]>([]);
  readonly status = signal("queued");
  readonly error = signal("");
  readonly loading = signal(true);
  private position = { run: "", cursor: null as string | null };
  private version = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  ngOnChanges(changes: SimpleChanges) {
    const previous = changes["task"]?.previousValue as Task | undefined;
    const changed = Boolean(changes["task"]) && previous?.id !== this.task.id;
    if (changed) {
      this.rows.set([]);
      this.position = { run: "", cursor: null };
      this.runId.set("");
      this.tab.set(this.initialTab);
      this.status.set(this.task.state);
      this.error.set("");
    }
    if (changed || changes["connected"]) {
      const version = ++this.version;
      clearTimeout(this.timer);
      this.loading.set(this.connected);
      if (this.connected) void this.poll(version);
    }
  }
  ngOnDestroy() {
    this.version++;
    clearTimeout(this.timer);
  }
  private async poll(version: number) {
    let delay = 1500;
    try {
      const id = this.task.id,
        run = await latestRun(id);
      if (version !== this.version) return;
      if (this.position.run !== run.id) {
        this.position = { run: run.id, cursor: null };
        this.rows.set([]);
      }
      this.runId.set(run.id);
      const page = await events(run.id, this.position.cursor);
      if (version !== this.version) return;
      this.position.cursor = page.next_cursor;
      const merged = new Map(this.rows().map((row) => [row.sequence, row]));
      for (const row of page.items) merged.set(row.sequence, row);
      this.rows.set([...merged.values()].slice(-500));
      this.status.set(run.state);
      this.stateChange.emit({ id, state: run.state });
      this.error.set("");
      if (page.has_more) delay = 50;
    } catch (cause) {
      if (version === this.version) this.error.set(errorText(cause));
    } finally {
      if (version === this.version) {
        this.loading.set(false);
        this.timer = setTimeout(() => void this.poll(version), delay);
      }
    }
  }
  moveTab(event: KeyboardEvent) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const index = this.tabs.indexOf(this.tab());
    const next =
      this.tabs[
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? this.tabs.length - 1
            : (index +
                (event.key === "ArrowRight" ? 1 : -1) +
                this.tabs.length) %
              this.tabs.length
      ];
    this.tab.set(next);
    document.getElementById("task-tab-" + next)?.focus();
  }
  date(value: string) {
    return new Date(value).toLocaleString();
  }
  eventText(event: ActivityEvent) {
    if (
      event.kind === "run.state_changed" &&
      typeof event.data["to"] === "string"
    )
      return stateLabel[event.data["to"]] ?? "State updated";
    if (typeof event.data["message"] === "string")
      return event.data["message"].slice(0, 4000);
    return event.kind.replaceAll(".", " ").replaceAll("_", " ");
  }
}
