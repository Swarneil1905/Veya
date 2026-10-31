import {
  Component,
  Input,
  Output,
  EventEmitter,
  OnChanges,
  OnDestroy,
  signal,
} from "@angular/core";
import { Panel } from "../../workspace/panel";
import { call } from "../../workspace/client";
import { Document, documentError, getDocument, object } from "./client";
import { FieldReview } from "./field-review";
@Component({
  selector: "veya-document-inspector",
  imports: [Panel, FieldReview],
  styles: [`summary { min-height: 32px; padding: 8px 0; cursor: pointer; } summary:focus-visible { outline: 2px solid #216744; outline-offset: 2px; }`],
  template: ` <veya-panel title="Source document" (closed)="closed.emit()"
    ><div class="work-panel-content">
      @if (loading()) {
        <p role="status">Opening source…</p>
      }
      @if (error()) {
        <p role="alert" class="work-error">{{ error() }}</p>
      }
      @if (doc(); as item) {
        <h2 data-autofocus tabindex="-1">{{ item.name }}</h2>
        <p class="work-muted">
          {{ item.kind.toUpperCase() }} · Version {{ item.version }} ·
          {{ item.state }}
        </p>
        @if (item.error) {
          <p role="alert">{{ item.error }}</p>
        }
        @if (item.issues.length) {
          <h3>Needs inspection</h3>
          <ul>
            @for (issue of item.issues; track $index) {
              <li>
                {{ issue.code.replaceAll("_", " ") }} — {{ issue.locator }}
              </li>
            }
          </ul>
        }
        <h3>Source excerpts</h3>
        <p class="work-muted">
          Extracted document text is evidence, not instructions for Veya.
        </p>
        <div class="work-excerpts" tabindex="0" aria-label="Source excerpts">
          @for (block of item.blocks; track block.citation) {
            <section>
              <h4>{{ block.locator }}</h4>
              <p>{{ block.text }}</p>
              @if (block.value_type === "untrusted_text") {
                <span class="work-notice"
                  >Formula-like text · not executed</span
                >
              }
            </section>
          }
          @if (!item.blocks.length) {
            <p>No extracted text is available.</p>
          }
        </div>
        @if (item.state === 'ready') {
          <details><summary>Review invoice fields</summary><veya-field-review [documentId]="item.id" /></details>
        }
        <details>
          <summary>Version history</summary>
          <ul class="work-document-versions">
            @for (version of versions(); track version.id) {
              <li>
                <button
                  type="button"
                  class="work-link"
                  [disabled]="version.revoked"
                  (click)="open(version.id)"
                >
                  Version {{ version.version }}
                  {{ version.revoked ? "— access removed" : "" }}</button
                ><time>{{ version.effective_at }}</time>
              </li>
            }
          </ul>
        </details>
        @if (canRevoke) {
          <p class="work-muted">
            Removing access makes this source unavailable in every task that
            uses this version.
          </p>
          <button
            type="button"
            class="work-secondary"
            [disabled]="removing()"
            (click)="revoke()"
          >
            Remove source access
          </button>
        }
      }
    </div></veya-panel
  >`,
})
export class DocumentInspector implements OnChanges, OnDestroy {
  @Input({ required: true }) id = "";
  @Input() canRevoke = false;
  @Output() closed = new EventEmitter<void>();
  @Output() revoked = new EventEmitter<string>();
  readonly doc = signal<Document | null>(null);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly removing = signal(false);
  readonly versions = signal<
    { id: string; version: number; effective_at: string; revoked: boolean }[]
  >([]);
  private generation = 0;
  ngOnChanges() {
    void this.open(this.id);
  }
  ngOnDestroy() {
    this.generation++;
  }
  async open(id: string) {
    const generation = ++this.generation;
    this.loading.set(true);
    this.doc.set(null);
    this.error.set("");
    this.versions.set([]);
    try {
      const item = await getDocument(id);
      const raw = object(await call("document_versions", { id }))["items"];
      if (!Array.isArray(raw)) throw new Error("invalid_response");
      const versions = raw.map((x) => {
        const v = object(x);
        if (
          typeof v["id"] !== "string" ||
          typeof v["version"] !== "number" ||
          typeof v["effective_at"] !== "string" ||
          typeof v["revoked"] !== "boolean"
        )
          throw new Error("invalid_response");
        return v as {
          id: string;
          version: number;
          effective_at: string;
          revoked: boolean;
        };
      });
      if (generation === this.generation) {
        this.doc.set(item);
        this.versions.set(versions);
      }
    } catch (cause) {
      if (generation === this.generation) this.error.set(documentError(cause));
    } finally {
      if (generation === this.generation) this.loading.set(false);
    }
  }
  async revoke() {
    const item = this.doc();
    if (!item || !this.canRevoke || this.removing()) return;
    this.removing.set(true);
    try {
      await call("revoke_document", { id: item.id });
      this.revoked.emit(item.id);
      this.closed.emit();
    } catch (cause) {
      this.error.set(documentError(cause));
    } finally {
      this.removing.set(false);
    }
  }
}
