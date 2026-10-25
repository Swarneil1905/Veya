import {
  Component,
  Input,
  Output,
  EventEmitter,
  OnInit,
  OnDestroy,
  signal,
} from "@angular/core";
import { call, isNative } from "../../workspace/client";
import {
  Document,
  document,
  documentError,
  encoded,
  getDocument,
  object,
} from "../documents/client";
import { DocumentInspector } from "../documents/document-inspector";
type Entry = {
  key: string;
  name: string;
  id?: string;
  content?: string;
  error: string;
  state: string;
  kind?: string;
};
@Component({
  selector: "veya-attachments",
  imports: [DocumentInspector],
  template: ` <section
      class="work-attachments"
      aria-labelledby="attachment-heading"
    >
      <div class="work-section-heading">
        <h3 id="attachment-heading">Documents</h3>
        <span>{{ rows().length }} / 10</span>
      </div>
      <p class="work-muted">
        Text PDF, CSV or XLSX · up to 512 KiB each. Review source text before
        saving.
      </p>
      <div class="work-document-actions">
        @if (native) {
          <button
            type="button"
            class="work-secondary"
            [disabled]="disabled || busy() || rows().length >= 10"
            (click)="pick(false)"
          >
            <i class="ph ph-paperclip" aria-hidden="true"></i>Add files</button
          ><button
            type="button"
            class="work-link"
            [disabled]="disabled || busy() || rows().length >= 10"
            (click)="pick(true)"
          >
            Choose folder
          </button>
        } @else {
          <label class="work-secondary work-file-picker"
            >Add files<input
              type="file"
              multiple
              accept=".pdf,.csv,.xlsx"
              [disabled]="disabled || busy() || rows().length >= 10"
              (change)="files($event)"
              aria-label="Add document files"
          /></label>
        }
      </div>
      @if (native) {
        <p class="work-muted">Folders import top-level documents only.</p>
      }
      @if (notice()) {
        <p role="status" class="work-notice">{{ notice() }}</p>
      }
      <ul class="work-document-list" aria-live="polite">
        @for (row of rows(); track row.key) {
          <li>
            <i class="ph ph-file-text" aria-hidden="true"></i>
            <div>
              <strong>{{ row.name }}</strong
              ><span>{{ row.kind?.toUpperCase() }} {{ row.state }}</span>
              @if (row.error) {
                <p class="work-error">{{ row.error }}</p>
              }
            </div>
            <div class="work-document-actions">
              @if (row.id) {
                <button
                  type="button"
                  class="work-link"
                  (click)="inspecting.set(row.id)"
                >
                  Inspect<span class="work-sr-only"> {{ row.name }}</span>
                </button>
              }
              @if (
                row.state === "failed" ||
                row.state === "queued" ||
                row.state === "processing"
              ) {
                <button
                  type="button"
                  class="work-link"
                  [disabled]="disabled || busy()"
                  (click)="retry(row)"
                >
                  Retry<span class="work-sr-only"> {{ row.name }}</span>
                </button>
              }
              <button
                type="button"
                class="work-link"
                [disabled]="disabled || busy()"
                (click)="remove(row)"
              >
                Remove<span class="work-sr-only"> {{ row.name }}</span>
              </button>
            </div>
          </li>
        }
      </ul>
      @if (busy()) {
        <p role="status">Importing document…</p>
      }
    </section>
    @if (inspecting(); as id) {
      <veya-document-inspector [id]="id" (closed)="inspecting.set(null)" />
    }`,
})
export class AttachmentList implements OnInit, OnDestroy {
  @Input() ids: string[] = [];
  @Input() disabled = false;
  @Output() changed = new EventEmitter<string[]>();
  @Output() blocked = new EventEmitter<boolean>();
  readonly native = isNative();
  readonly rows = signal<Entry[]>([]);
  readonly busy = signal(false);
  readonly notice = signal("");
  readonly inspecting = signal<string | null>(null);
  private destroyed = false;
  ngOnDestroy() {
    this.destroyed = true;
  }
  async ngOnInit() {
    if (!this.ids.length) return;
    this.rows.set(
      this.ids.map((id) => ({
        key: id,
        id,
        name: "Saved document",
        state: "loading",
        error: "",
      })),
    );
    this.busy.set(true);
    this.report();
    for (const id of this.ids) {
      try {
        const d = await getDocument(id);
        this.update(id, this.entry(d));
      } catch (cause) {
        this.update(id, { state: "failed", error: documentError(cause) });
      }
    }
    this.busy.set(false);
    this.report();
  }
  private entry(d: Document): Entry {
    return {
      key: d.id,
      id: d.id,
      name: d.name,
      kind: d.kind,
      state: d.state,
      error: d.error,
    };
  }
  private report() {
    if (this.destroyed) return;
    this.changed.emit(this.rows().flatMap((r) => (r.id ? [r.id] : [])));
    this.blocked.emit(
      this.busy() || this.rows().some((r) => r.state !== "ready"),
    );
  }
  private update(key: string, patch: Partial<Entry>) {
    this.rows.update((v) =>
      v.map((r) => (r.key === key ? { ...r, ...patch } : r)),
    );
    this.report();
  }
  async files(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = [...(input.files ?? [])];
    input.value = "";
    if (this.disabled || this.busy()) return;
    this.busy.set(true);
    this.report();
    try {
      for (const file of files) {
        if (this.rows().length >= 10) {
          this.notice.set("Choose up to 10 documents.");
          break;
        }
        const row: Entry = {
          key: crypto.randomUUID(),
          name: file.name,
          state: "queued",
          error: "",
        };
        this.rows.update((v) => [...v, row]);
        try {
          row.content = await encoded(file);
          await this.importRow(row);
        } catch (cause) {
          this.update(row.key, {
            state: "failed",
            error: documentError(cause),
          });
        }
      }
    } finally {
      this.busy.set(false);
      this.report();
    }
  }
  async pick(folder: boolean) {
    if (this.disabled || this.busy()) return;
    this.busy.set(true);
    this.notice.set("");
    this.report();
    try {
      const raw = await window.__TAURI__?.core.invoke("select_documents", {
        folder,
      });
      if (!Array.isArray(raw)) throw new Error("invalid_response");
      for (const value of raw) {
        if (this.rows().length >= 10) {
          this.notice.set("Choose up to 10 documents.");
          break;
        }
        const v = object(value);
        if (typeof v["name"] !== "string") throw new Error("invalid_response");
        const row: Entry = {
          key: crypto.randomUUID(),
          name: v["name"],
          state: "queued",
          error: "",
          content: typeof v["content"] === "string" ? v["content"] : undefined,
        };
        this.rows.update((items) => [...items, row]);
        if (typeof v["error"] === "string")
          this.update(row.key, { state: "failed", error: v["error"] });
        else await this.importRow(row);
      }
    } catch (cause) {
      this.notice.set(documentError(cause));
    } finally {
      this.busy.set(false);
      this.report();
    }
  }
  private async importRow(row: Entry) {
    try {
      if (!row.content) throw new Error("invalid_input");
      const d = document(
        await call("import_document", {
          request_id: row.key,
          name: row.name,
          content: row.content,
        }),
      );
      if (this.rows().some((r) => r.key !== row.key && r.id === d.id)) {
        this.rows.update((rows) => rows.filter((r) => r.key !== row.key));
        this.notice.set("This document is already attached.");
        return;
      }
      this.update(row.key, { ...this.entry(d), key: row.key });
      const ready = await getDocument(d.id, true);
      this.update(row.key, { ...this.entry(ready), key: row.key });
    } catch (cause) {
      this.update(row.key, { state: "failed", error: documentError(cause) });
    }
  }
  async retry(row: Entry) {
    if (this.disabled || this.busy()) return;
    this.busy.set(true);
    this.report();
    try {
      if (row.id) {
        await call("retry_document", { id: row.id });
        const d = await getDocument(row.id, true);
        this.update(row.key, { ...this.entry(d), key: row.key });
      } else await this.importRow(row);
    } catch (cause) {
      this.update(row.key, { state: "failed", error: documentError(cause) });
    } finally {
      this.busy.set(false);
      this.report();
    }
  }
  remove(row: Entry) {
    if (this.disabled || this.busy()) return;
    this.rows.update((v) => v.filter((r) => r.key !== row.key));
    this.report();
  }
}
