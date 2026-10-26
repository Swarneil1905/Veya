import {
  Component,
  Input,
  OnChanges,
  SimpleChanges,
  signal,
} from "@angular/core";
import { call } from "../../workspace/client";
import {
  connections,
  Connections,
  providerError,
} from "../settings/provider-client";
@Component({
  selector: "veya-execution-controls",
  template: ` <section
    class="work-execution-controls"
    aria-label="Task execution"
  >
    @if (state === "queued") {
      @if (settings(); as s) {
        @if (s.active.length) {
          <p>Ready for read-only work with {{ names() }}.</p>
          <p class="work-muted">
            This task can read its attachments and calculate. It cannot send
            messages or change business records.
          </p>
          @if (remote()) {
            <label class="work-check-label"
              ><input
                type="checkbox"
                [checked]="consent"
                [disabled]="disabled || pending()"
                (change)="consent = checked($event)"
              />I permit this task and its attachments as internal data for the
              displayed hosted providers, including fallback. Provider charges
              may apply.</label
            >
          }
          <button
            class="work-primary"
            [disabled]="
              disabled || pending() || !runId || (remote() && !consent)
            "
            (click)="start()"
          >
            {{ pending() ? "Starting…" : "Start read-only task" }}
          </button>
        } @else {
          <p class="work-notice">
            Saved and queued. Test and activate a model in Connection to start
            this task.
          </p>
        }
      } @else {
        <p class="work-muted">Checking model connection…</p>
      }
      <button
        class="work-link-button"
        [disabled]="disabled || pending()"
        (click)="load()"
      >
        Refresh model connection
      </button>
    }
    @if (state === "running") {
      <button
        class="work-secondary"
        [disabled]="disabled || pending()"
        (click)="cancel()"
      >
        Cancel task
      </button>
    }
    @if (error()) {
      <p class="work-error" role="alert">{{ error() }}</p>
    }
    @if (notice()) {
      <p role="status">{{ notice() }}</p>
    }
  </section>`,
})
export class ExecutionControls implements OnChanges {
  @Input() runId = "";
  @Input() state = "queued";
  @Input() disabled = false;
  readonly settings = signal<Connections | null>(null);
  readonly error = signal("");
  readonly notice = signal("");
  readonly pending = signal(false);
  consent = false;
  ngOnChanges(changes: SimpleChanges) {
    if (changes["runId"]) {
      this.consent = false;
      this.notice.set("");
      this.error.set("");
    }
    if (this.state === "queued" && !this.settings() && !this.disabled)
      void this.load();
  }
  checked(event: Event) {
    return (event.target as HTMLInputElement).checked;
  }
  remote() {
    return this.settings()?.active.some((p) => p.profile === "remote") ?? false;
  }
  names() {
    return this.settings()
      ?.active.map((p) => p.model_name + " (" + p.profile + ")")
      .join(" → ");
  }
  async load() {
    try {
      this.settings.set(await connections());
      this.error.set("");
      this.consent = false;
    } catch (e) {
      this.error.set(providerError(e));
    }
  }
  async start() {
    if (
      this.disabled ||
      this.pending() ||
      !this.settings()?.active.length ||
      (this.remote() && !this.consent)
    )
      return;
    this.pending.set(true);
    this.error.set("");
    try {
      await call("execute_run", {
        run_id: this.runId,
        expected_selection: this.settings()!.active_fingerprints,
        allow_remote: this.consent,
      });
      this.notice.set("Task started. Progress appears in Activity.");
    } catch (e) {
      this.error.set(providerError(e));
    } finally {
      this.pending.set(false);
    }
  }
  async cancel() {
    if (this.disabled || this.pending()) return;
    this.pending.set(true);
    try {
      await call("cancel_run", { run_id: this.runId });
      this.notice.set(
        "Cancellation recorded. Late responses will not become results.",
      );
    } catch (e) {
      this.error.set(providerError(e));
    } finally {
      this.pending.set(false);
    }
  }
}
