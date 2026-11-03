import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { call, errorText } from "../../workspace/client";

type Lesson = {
  id: string;
  revision: number;
  content: string;
  topic: string;
  state: string;
  source_run: string;
  expires_at: string;
  expired: boolean;
};

@Component({
  selector: "veya-memory-review",
  styles: [
    `
      :host {
        display: block;
        margin-top: 24px;
        max-width: 880px;
      }
      textarea {
        display: block;
        width: 100%;
        min-height: 88px;
        padding: 12px;
        font: inherit;
        box-sizing: border-box;
        border: 1px solid var(--work-line);
        border-radius: 4px;
        background: var(--work-bg);
      }
      .lesson {
        padding: 20px 0;
        border-bottom: 1px solid var(--work-line);
      }
      .lesson-heading {
        display: flex;
        align-items: baseline;
        gap: 12px;
        justify-content: space-between;
        flex-wrap: wrap;
        margin-bottom: 12px;
      }
      .lesson-heading h3, .lesson-heading p { margin: 0; }
      .lesson-source { margin: 12px 0; color: var(--work-muted); }
      .lesson-source summary { cursor: pointer; min-height: 32px; padding: 6px 0; }
      .lesson-source p { margin: 6px 0 12px; }
      .actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 12px;
      }
      code {
        overflow-wrap: anywhere;
      }
      input {
        min-height: 36px;
        max-width: 100%;
        font: inherit;
      }
    `,
  ],
  template: `<section aria-labelledby="memory-title">
    <h2 id="memory-title">Reviewed lessons</h2>
    <p>
      Keep useful lessons from failed work. Only lessons you approve can inform
      future local-model tasks. They do not grant permissions or go to hosted providers.
    </p>
    <div class="actions">
      <button
        class="work-secondary"
        (click)="refresh()"
        [disabled]="!connected || busy()"
      >
        Refresh lessons
      </button>
      <button
        class="work-secondary"
        (click)="exportData()"
        [disabled]="!connected || busy()"
      >
        Export my lessons
      </button>
    </div>
    @if (!connected) {
      <p role="status">Connect to review lessons.</p>
    }
    @if (message()) {
      <p role="status">{{ message() }}</p>
    }
    @if (error()) {
      <p role="alert">{{ error() }}</p>
    }
    @if (busy()) {
      <p role="status">Updating lessons…</p>
    }
    @if (connected && !busy() && !items().length) {
      <p>
        No lessons yet. Open a failed task to propose a lesson from its
        recorded failure.
      </p>
    }
    @for (item of items(); track item.id) {
      <article class="lesson" [attr.aria-label]="'Lesson: ' + topicTitle(item.topic)">
        <div class="lesson-heading">
          <h3>{{ topicTitle(item.topic) }}</h3>
          <p class="work-muted">{{ statusLabel(item) }}</p>
        </div>
        <label [for]="'lesson-' + item.id">Lesson</label>
        <textarea
          [id]="'lesson-' + item.id"
          maxlength="2000"
          [value]="drafts[item.id] ?? item.content"
          (input)="edit(item.id, $event)"
          [disabled]="readOnly || busy() || item.state === 'retracted'"
        ></textarea>
        <details class="lesson-source">
          <summary>Source details</summary>
          <p>Revision {{ item.revision }} · Expires {{ item.expires_at.slice(0, 10) }}<br />Source run <code>{{ item.source_run }}</code></p>
        </details>
        <div class="actions">
          <button
            class="work-primary"
            (click)="review(item, 'activate')"
            [disabled]="
              readOnly || busy() || item.expired || item.state === 'retracted'
            "
          >
            {{
              item.state === "active"
                ? "Approve changes"
                : "Approve lesson"
            }}
          </button>
          <button
            class="work-secondary"
            (click)="review(item, 'retract')"
            [disabled]="readOnly || busy() || item.state === 'retracted'"
          >
            Retract
          </button>
          <button
            class="work-secondary"
            (click)="eraseId.set(item.id)"
            [disabled]="readOnly || busy()"
          >
            Erase…
          </button>
        </div>
        @if (eraseId() === item.id) {
          <div role="group" aria-label="Confirm memory erasure">
            <p>
              Erase this lesson and its historical text? Source tasks and audit
              identifiers will remain.
            </p>
            <div class="actions">
              <button
                class="work-secondary"
                (click)="erase(item)"
                [disabled]="busy()"
              >
                Confirm erase lesson</button
              ><button class="work-secondary" (click)="eraseId.set('')">
                Keep lesson
              </button>
            </div>
          </div>
        }
      </article>
    }
  </section>`,
})
export class MemoryReview implements OnChanges, OnDestroy {
  @Input() connected = false;
  @Input() readOnly = false;
  readonly items = signal<Lesson[]>([]);
  readonly busy = signal(false);
  readonly error = signal("");
  readonly message = signal("");
  readonly eraseId = signal("");
  drafts: Record<string, string> = {};
  topicTitle(topic: string) {
    const titles: Record<string, string> = {
      budget_exceeded: "Task exceeded its budget",
      interrupted_restart: "Task interrupted by a restart",
      invalid_output: "Result format needs correction",
      no_evidence: "Missing supporting evidence",
      unverified_citation: "Source citation needs verification",
      verification_failed: "Result could not be verified",
      no_progress: "Task stopped making progress",
    };
    return titles[topic] ?? topic.replaceAll("_", " ");
  }
  statusLabel(item: Lesson) {
    if (item.expired && item.state !== "retracted") return "Expired";
    return ({ draft: "Needs review", active: "In use", retracted: "Retracted" } as Record<string, string>)[item.state] ?? item.state;
  }
  private generation = 0;
  private disposed = false;
  edit(id: string, event: Event) {
    this.drafts[id] = (event.target as HTMLTextAreaElement).value;
  }
  ngOnChanges() {
    this.generation++;
    if (this.connected) void this.refresh();
    else {
      this.items.set([]);
      this.busy.set(false);
    }
  }
  ngOnDestroy() {
    this.disposed = true;
    this.generation++;
  }
  async refresh() {
    if (!this.connected || this.disposed) return;
    const generation = ++this.generation;
    this.busy.set(true);
    this.error.set("");
    try {
      const data = (await call("list_memories")) as { items: Lesson[] };
      if (generation === this.generation) this.items.set(data.items);
    } catch (e) {
      if (generation === this.generation) this.error.set(errorText(e));
    } finally {
      if (generation === this.generation) this.busy.set(false);
    }
  }
  async review(item: Lesson, action: "activate" | "retract") {
    if (!this.connected || this.disposed || this.readOnly || this.busy())
      return;
    this.busy.set(true);
    this.error.set("");
    this.message.set("");
    try {
      await call("review_memory", {
        id: item.id,
        revision: item.revision,
        content: this.drafts[item.id] ?? item.content,
        action,
      });
      delete this.drafts[item.id];
      await this.refresh();
      this.message.set(
        action === "activate"
          ? "Lesson approved for future tasks."
          : "Lesson retracted. It will not inform future tasks.",
      );
    } catch (e) {
      this.error.set(
        e instanceof Error && e.message === "memory_conflict"
          ? "A different active lesson covers this failure. Retract it before approving this one."
          : `${errorText(e)} Your draft is preserved; refresh to check the current revision.`,
      );
    } finally {
      this.busy.set(false);
    }
  }
  async erase(item: Lesson) {
    if (!this.connected || this.disposed || this.readOnly || this.busy())
      return;
    this.busy.set(true);
    try {
      await call("erase_memory", { id: item.id, revision: item.revision });
      delete this.drafts[item.id];
      this.eraseId.set("");
      await this.refresh();
      this.message.set(
        "Lesson text erased. Source task and audit identifiers remain.",
      );
    } catch (e) {
      this.error.set(errorText(e));
    } finally {
      this.busy.set(false);
    }
  }
  async exportData() {
    if (!this.connected || this.disposed || this.busy()) return;
    this.busy.set(true);
    try {
      const data = await call("export_memories");
      if (!this.connected || this.disposed) return;
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "veya-reviewed-lessons.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.message.set("Your lessons were exported as JSON.");
    } catch (e) {
      this.error.set(errorText(e));
    } finally {
      this.busy.set(false);
    }
  }
}
