import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { call } from "../../workspace/client";
import { Document, document, documentError, object } from "./client";
import { DocumentInspector } from "./document-inspector";
@Component({
  selector: "veya-task-documents",
  imports: [DocumentInspector],
  template: ` <h3>Source documents</h3>
    @if (error()) {
      <p role="alert">{{ error() }}</p>
    }
    @if (loading()) {
      <p role="status">Loading documents…</p>
    }
    @if (!loading() && !items().length && !error()) {
      <p class="work-muted">No documents were attached to this task.</p>
    }
    <ul class="work-document-list">
      @for (item of items(); track item.id) {
        <li>
          <i class="ph ph-file-text" aria-hidden="true"></i>
          <div>
            <strong>{{ item.name }}</strong
            ><span
              >{{ item.kind.toUpperCase() }} · Version {{ item.version }} ·
              {{
                item.state === "revoked" ? "Source unavailable" : item.state
              }}</span
            >
          </div>
          <button
            class="work-link"
            type="button"
            [disabled]="item.state === 'revoked'"
            (click)="selected.set(item.id)"
          >
            Inspect<span class="work-sr-only"> {{ item.name }}</span>
          </button>
        </li>
      }
    </ul>
    @if (selected(); as id) {
      <veya-document-inspector
        [id]="id"
        [canRevoke]="!readOnly"
        (revoked)="load()"
        (closed)="selected.set(null)"
      />
    }`,
})
export class TaskDocuments implements OnChanges, OnDestroy {
  @Input({ required: true }) taskId = "";
  @Input() readOnly = true;
  readonly items = signal<Document[]>([]);
  readonly error = signal("");
  readonly loading = signal(false);
  readonly selected = signal<string | null>(null);
  private generation = 0;
  ngOnChanges() {
    void this.load();
  }
  ngOnDestroy() {
    this.generation++;
  }
  async load() {
    const generation = ++this.generation;
    this.items.set([]);
    this.error.set("");
    this.loading.set(true);
    try {
      const v = object(await call("task_documents", { task_id: this.taskId }));
      if (!Array.isArray(v["items"])) throw new Error("invalid_response");
      if (generation === this.generation)
        this.items.set(v["items"].map(document));
    } catch (cause) {
      if (generation === this.generation) this.error.set(documentError(cause));
    } finally {
      if (generation === this.generation) this.loading.set(false);
    }
  }
}
