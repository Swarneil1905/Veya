import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { call, errorText } from "../../workspace/client";
import { Panel } from "../../workspace/panel";
import { Citation, citation, object } from "../documents/client";
type ResultItem = {
  id: string;
  name: string;
  mime_type: string;
  available: boolean;
  preview: string;
  claims: { text: string; citations: Citation[] }[];
  exceptions: string[];
};
@Component({
  selector: "veya-results",
  imports: [Panel],
  template: ` <div class="work-section-heading">
      <h3>Results and evidence</h3>
      <button
        type="button"
        class="work-link"
        [disabled]="loading() || !runId"
        (click)="load(true)"
      >
        Refresh results
      </button>
    </div>
    @if (error()) {
      <p role="alert" class="work-error">{{ error() }}</p>
    }
    @if (loading()) {
      <p role="status">Loading results…</p>
    }
    @if (!loading() && !items().length && !error()) {
      <p class="work-muted">
        No output artifacts have been recorded for this run. Partial activity is
        not a completed result.
      </p>
    }
    @for (item of items(); track item.id) {
      <article class="work-result">
        <h4>{{ item.name }}</h4>
        <p class="work-muted">{{ item.mime_type }}</p>
        @if (!item.available) {
          <p role="status">
            Output unavailable. Its stored bytes could not be verified.
          </p>
        } @else {
          <button
            type="button"
            class="work-secondary"
            [disabled]="downloading() === item.id"
            (click)="download(item)"
          >
            Save output<span class="work-sr-only"> {{ item.name }}</span>
          </button>
          @if (item.claims.length) {
            @for (claim of item.claims; track $index) {
              <section class="work-claim">
                <p>{{ claim.text }}</p>
                @if (!claim.citations.length) {
                  <p class="work-muted">
                    No source evidence supplied for this claim.
                  </p>
                }
                @for (ref of claim.citations; track $index) {
                  @if (ref.available) {
                    <button
                      type="button"
                      class="work-link"
                      (click)="open(ref.citation)"
                    >
                      {{ ref.source }} · {{ ref.locator }} · v{{ ref.version }}
                    </button>
                  } @else {
                    <p class="work-error">Source evidence unavailable</p>
                  }
                }
              </section>
            }
          } @else if (item.preview) {
            <details>
              <summary>Inspect output text</summary>
              <pre class="work-output-preview">{{ item.preview }}</pre>
              <p class="work-muted">
                Preview limited to the first 16 KiB. Save output for the
                complete file.
              </p>
            </details>
          }
        }
        @if (item.exceptions.length) {
          <h5>Unresolved exceptions</h5>
          <ul>
            @for (exception of item.exceptions; track $index) {
              <li>{{ exception }}</li>
            }
          </ul>
        }
      </article>
    }
    @if (hasMore()) {
      <button
        type="button"
        class="work-secondary"
        [disabled]="loading()"
        (click)="load()"
      >
        More outputs
      </button>
    }
    @if (sourceOpen()) {
      <veya-panel title="Source evidence" (closed)="closeSource()"
        ><div class="work-panel-content">
          @if (sourceLoading()) {
            <p role="status">Checking source access…</p>
          }
          @if (source(); as ref) {
            @if (ref.available) {
              <h2 data-autofocus tabindex="-1">{{ ref.source }}</h2>
              <p class="work-muted">
                Version {{ ref.version }} · {{ ref.locator }}
              </p>
              <blockquote class="work-source-excerpt">
                {{ ref.text }}
              </blockquote>
            } @else {
              <h2>Evidence unavailable</h2>
              <p role="status">{{ ref.reason }}</p>
            }
          }
          @if (sourceError()) {
            <p role="alert">{{ sourceError() }}</p>
          }
        </div></veya-panel
      >
    }`,
})
export class ResultPanel implements OnChanges, OnDestroy {
  @Input({ required: true }) runId = "";
  readonly items = signal<ResultItem[]>([]);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly hasMore = signal(false);
  readonly downloading = signal("");
  readonly sourceOpen = signal(false);
  readonly sourceLoading = signal(false);
  readonly source = signal<Citation | null>(null);
  readonly sourceError = signal("");
  private cursor = 0;
  private generation = 0;
  private sourceGeneration = 0;
  ngOnChanges() {
    void this.load(true);
  }
  ngOnDestroy() {
    this.generation++;
    this.sourceGeneration++;
  }
  async load(reset = false) {
    if (!this.runId) return;
    if (this.loading() && !reset) return;
    const generation = ++this.generation;
    this.loading.set(true);
    this.error.set("");
    if (reset) {
      this.cursor = 0;
      this.items.set([]);
      this.hasMore.set(false);
    }
    try {
      const v = object(
        await call("list_results", { run_id: this.runId, after: this.cursor }),
      );
      if (
        !Array.isArray(v["items"]) ||
        typeof v["has_more"] !== "boolean" ||
        !Number.isSafeInteger(v["next_cursor"])
      )
        throw new Error("invalid_response");
      const items = v["items"].map((raw) => {
        const r = object(raw);
        if (
          !["id", "name", "mime_type", "preview"].every(
            (k) => typeof r[k] === "string",
          ) ||
          typeof r["available"] !== "boolean" ||
          !Array.isArray(r["claims"]) ||
          !Array.isArray(r["exceptions"])
        )
          throw new Error("invalid_response");
        for (const claim of r["claims"]) {
          const c = object(claim);
          if (typeof c["text"] !== "string" || !Array.isArray(c["citations"]))
            throw new Error("invalid_response");
          for (const ref of c["citations"]) {
            const x = object(ref);
            if (
              typeof x["available"] !== "boolean" ||
              typeof x["citation"] !== "string"
            )
              throw new Error("invalid_response");
          }
        }
        return r as ResultItem;
      });
      if (generation === this.generation) {
        this.items.update((old) => [...old, ...items]);
        this.hasMore.set(v["has_more"]);
        this.cursor = Number(v["next_cursor"]);
      }
    } catch (cause) {
      if (generation === this.generation) this.error.set(errorText(cause));
    } finally {
      if (generation === this.generation) this.loading.set(false);
    }
  }
  closeSource() {
    this.sourceGeneration++;
    this.sourceOpen.set(false);
  }
  async open(id: string) {
    const generation = ++this.sourceGeneration;
    this.sourceOpen.set(true);
    this.sourceLoading.set(true);
    this.source.set(null);
    this.sourceError.set("");
    try {
      const ref = await citation(id);
      if (generation === this.sourceGeneration) this.source.set(ref);
    } catch {
      if (generation === this.sourceGeneration)
        this.sourceError.set(
          "Source evidence could not be checked. Reconnect and try again.",
        );
    } finally {
      if (generation === this.sourceGeneration) this.sourceLoading.set(false);
    }
  }
  async download(item: ResultItem) {
    if (this.downloading()) return;
    this.downloading.set(item.id);
    try {
      const v = object(await call("download_artifact", { id: item.id }));
      if (typeof v["content"] !== "string") throw new Error("invalid_response");
      const bytes = Uint8Array.from(atob(v["content"]), (c) => c.charCodeAt(0));
      const url = URL.createObjectURL(
        new Blob([bytes], { type: "application/octet-stream" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = item.name.replace(/[\\/:*?"<>|]/g, "_");
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      this.error.set(errorText(cause));
    } finally {
      this.downloading.set("");
    }
  }
}
