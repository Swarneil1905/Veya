import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { Panel } from "../../workspace/panel";
import { errorText } from "../../workspace/client";
import {
  listing,
  trajectory,
  reviewTrace,
  Summary,
  TraceView,
} from "../evaluations/client";
@Component({
  selector: "veya-trajectory-review",
  imports: [Panel],
  template: ` <section aria-label="Trajectory review">
      <div class="work-queue-toolbar">
        <p>Review source evidence before it can enter a dataset.</p>
        <button
          class="work-secondary"
          (click)="refresh()"
          [disabled]="!connected || loading()"
        >
          Refresh examples
        </button>
      </div>
      @if (!connected) {
        <p role="status">Connect to review recorded examples.</p>
      }
      @if (error()) {
        <p role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status">Loading review queue…</p>
      }
      @if (!loading() && connected && !items().length && !error()) {
        <div class="work-empty">
          <h2>No examples awaiting review</h2>
          <p>
            Only normalized traces appear here. Quarantined traces remain
            outside dataset builds.
          </p>
        </div>
      }
      <ul class="research-list">
        @for (item of items(); track item.id) {
          <li>
            <button class="research-row" (click)="open(item.id)">
              <span
                ><strong>{{ item.title }}</strong
                ><small
                  >{{ item.count }} recorded steps · {{ item.status }}</small
                ></span
              ><span>{{
                item.source === "synthetic"
                  ? "Synthetic fixture"
                  : "Model result"
              }}</span
              ><i class="ph ph-arrow-right" aria-hidden="true"></i>
            </button>
          </li>
        }
      </ul>
      @if (next() !== null) {
        <button class="work-secondary" (click)="more()" [disabled]="loading()">
          More examples
        </button>
      }
    </section>
    @if (selected(); as data) {
      <veya-panel title="Review example" (closed)="close()"
        ><div class="work-panel-content">
          <h2 data-autofocus tabindex="-1">{{ data.trace.case_id }}</h2>
          <p>
            {{
              data.trace.source === "synthetic"
                ? "Synthetic fixture"
                : "Model result"
            }}
            · {{ data.trace.split }} partition · {{ data.trace.family }}
          </p>
          @if (!data.authorized) {
            <p role="alert">
              Source authorization is missing or withdrawn. This example cannot
              be approved.
            </p>
          }
          <ol class="research-events">
            @for (step of data.trace.events; track step.sequence) {
              <li>
                <strong>{{ step.kind }} {{ step.operation ?? "" }}</strong>
                <p>{{ step.content }}</p>
                <small
                  >{{ step.run_id }} · attempt {{ step.attempt }} ·
                  {{ step.model_id }}</small
                >
              </li>
            }
          </ol>
          <label for="review-quality">Quality tag</label
          ><select
            id="review-quality"
            [value]="tag()"
            (change)="setTag($event)"
            [disabled]="saving()"
          >
            <option value="useful">Useful</option>
            <option value="incorrect">Incorrect</option>
            <option value="incomplete">Incomplete</option>
            <option value="sensitive">Sensitive</option>
          </select>
          <label for="review-note">Review note</label
          ><textarea
            id="review-note"
            rows="3"
            maxlength="2000"
            [value]="note()"
            (input)="setNote($event)"
            [disabled]="saving()"
          ></textarea>
          @if (saveError()) {
            <p role="alert">{{ saveError() }}</p>
          }
          @if (message()) {
            <p role="status">{{ message() }}</p>
          }
          <div class="work-form-actions">
            <button
              class="work-secondary"
              (click)="save('rejected')"
              [disabled]="saving() || !connected || readOnly || !note().trim()"
            >
              Reject example</button
            ><button
              class="work-primary"
              (click)="save('approved')"
              [disabled]="
                saving() ||
                !connected ||
                readOnly ||
                !data.authorized ||
                !note().trim() ||
                tag() !== 'useful'
              "
            >
              Approve example
            </button>
          </div>
          <h3>Review history</h3>
          @if (!data.history.length) {
            <p>Not reviewed yet.</p>
          }
          <ol>
            @for (item of data.history; track item.revision) {
              <li>
                {{ item.decision }} by {{ item.reviewer }} · revision
                {{ item.revision }}
                <p>{{ item.note }}</p>
              </li>
            }
          </ol>
        </div></veya-panel
      >
    }`,
})
export class TrajectoryReview implements OnChanges, OnDestroy {
  @Input() connected = false;
  @Input() readOnly = true;
  readonly items = signal<Summary[]>([]);
  readonly next = signal<number | null>(null);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly selected = signal<TraceView | null>(null);
  readonly note = signal("");
  readonly tag = signal("useful");
  readonly saving = signal(false);
  readonly saveError = signal("");
  readonly message = signal("");
  private version = 0;
  private readonly drafts = new Map<string, { note: string; tag: string }>();
  ngOnChanges() {
    void this.refresh();
  }
  ngOnDestroy() {
    this.version++;
  }
  async refresh() {
    this.saving.set(false);
    this.selected.set(null);
    this.items.set([]);
    this.next.set(null);
    await this.load(0);
  }
  async more() {
    if (this.next() !== null) await this.load(this.next()!);
  }
  private async load(after: number) {
    const v = ++this.version;
    this.error.set("");
    if (!this.connected) {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    try {
      const data = await listing("trajectories", after);
      if (v === this.version) {
        this.items.update((items) =>
          after ? [...items, ...data.items] : data.items,
        );
        this.next.set(data.next_cursor);
      }
    } catch (e) {
      if (v === this.version) this.error.set(errorText(e));
    } finally {
      if (v === this.version) this.loading.set(false);
    }
  }
  async open(id: string) {
    if (this.loading()) return;
    const v = ++this.version;
    this.error.set("");
    try {
      const data = await trajectory(id);
      if (v === this.version) {
        this.selected.set(data);
        const draft = this.drafts.get(id);
        this.note.set(draft?.note ?? "");
        this.tag.set(draft?.tag ?? "useful");
        this.message.set("");
        this.saveError.set("");
      }
    } catch (e) {
      if (v === this.version) this.error.set(errorText(e));
    }
  }
  close() {
    this.version++;
    this.selected.set(null);
    this.saving.set(false);
  }
  setNote(e: Event) {
    this.note.set((e.target as HTMLTextAreaElement).value);
    this.rememberDraft();
  }
  setTag(e: Event) {
    this.tag.set((e.target as HTMLSelectElement).value);
    this.rememberDraft();
  }
  private rememberDraft() {
    const key = this.selected()?.trace.id;
    if (key) this.drafts.set(key, { note: this.note(), tag: this.tag() });
  }
  async save(decision: "approved" | "rejected") {
    const data = this.selected();
    if (
      !data ||
      this.saving() ||
      !this.connected ||
      this.readOnly ||
      !this.note().trim()
    )
      return;
    const v = this.version;
    this.saving.set(true);
    this.saveError.set("");
    this.message.set("");
    try {
      const updated = await reviewTrace(data, decision, this.note(), [
        this.tag(),
      ]);
      if (v === this.version) {
        this.selected.set(updated);
        this.drafts.delete(updated.trace.id);
        this.items.update((items) =>
          items.map((i) =>
            i.id === data.trace.id ? { ...i, status: decision } : i,
          ),
        );
        this.message.set("Review saved. Original evidence preserved.");
      }
    } catch (e) {
      if (v === this.version) this.saveError.set(errorText(e));
    } finally {
      if (v === this.version) this.saving.set(false);
    }
  }
}
