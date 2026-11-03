import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { call, errorText } from "../../workspace/client";
type Contribution = {
  id: string;
  revision: number;
  available: boolean;
  current_state: string;
  snapshot: { content: string; source_run: string } | null;
  reason: string;
};
@Component({
  selector: "veya-memory-evidence",
  template: `<section aria-label="Lesson evidence">
    <h3>Lessons used</h3>
    @if (error()) {
      <p role="alert">{{ error() }}</p>
    }
    @if (message()) {
      <p role="status">{{ message() }}</p>
    }
    @if (!items().length) {
      <p class="work-muted">No reviewed lessons recorded for this attempt.</p>
    }
    @for (item of items(); track item.id) {
      <article>
        <p>
          <strong>Revision {{ item.revision }}</strong> ·
          {{ item.current_state }}
        </p>
        @if (item.available && item.snapshot) {
          <p>{{ item.snapshot.content }}</p>
          <p class="work-muted">Source run: {{ item.snapshot.source_run }}</p>
        } @else {
          <p>
            Lesson text unavailable: {{ item.reason }}. Its contribution remains
            recorded.
          </p>
        }
      </article>
    }
    <button
      class="work-secondary"
      (click)="refresh()"
      [disabled]="!connected || !runId || busy()"
    >
      Refresh lesson evidence
    </button>
    @if (state === "failed") {
      <button
        class="work-secondary"
        (click)="propose()"
        [disabled]="!connected || !runId || readOnly || busy()"
      >
        Propose lesson from failure
      </button>
    }
  </section>`,
})
export class MemoryEvidence implements OnChanges, OnDestroy {
  @Input() runId = "";
  @Input() state = "";
  @Input() connected = false;
  @Input() readOnly = false;
  readonly items = signal<Contribution[]>([]);
  readonly error = signal("");
  readonly message = signal("");
  readonly busy = signal(false);
  private generation = 0;
  ngOnDestroy() {
    this.generation++;
  }
  ngOnChanges() {
    this.generation++;
    this.items.set([]);
    this.error.set("");
    this.message.set("");
    if (this.connected && this.runId) void this.refresh();
  }
  async refresh() {
    const generation = ++this.generation;
    this.busy.set(true);
    try {
      const data = (await call("memory_evidence", { run_id: this.runId })) as {
        items: Contribution[];
      };
      if (generation === this.generation) this.items.set(data.items);
    } catch (e) {
      if (generation === this.generation) this.error.set(errorText(e));
    } finally {
      if (generation === this.generation) this.busy.set(false);
    }
  }
  async propose() {
    if (!this.connected || !this.runId || this.readOnly || this.busy()) return;
    this.busy.set(true);
    this.error.set("");
    try {
      await call("propose_memory", { run_id: this.runId });
      this.message.set(
        "Candidate saved. Open Data review → Reviewed lessons to edit and approve it.",
      );
    } catch (e) {
      this.error.set(
        e instanceof Error && e.message === "unsupported_failure"
          ? "This failure needs investigation before Veya can suggest a lesson."
          : errorText(e),
      );
    } finally {
      this.busy.set(false);
    }
  }
}
