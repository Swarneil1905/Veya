import { Component, Input, OnChanges, OnDestroy, signal } from "@angular/core";
import { Panel } from "../../workspace/panel";
import { errorText } from "../../workspace/client";
import { listing, report, Summary, Report, Outcome } from "./client";
@Component({
  selector: "veya-evaluations",
  imports: [Panel],
  template: ` <section aria-label="Evaluation reports">
      <div class="work-queue-toolbar">
        <p>Compare recorded behavior before changing a model.</p>
        <button
          class="work-secondary"
          (click)="refresh()"
          [disabled]="!connected || loading()"
        >
          Refresh reports
        </button>
      </div>
      @if (!connected) {
        <p role="status">Connect to your workspace to inspect evaluations.</p>
      }
      @if (error()) {
        <p role="alert">{{ error() }}</p>
      }
      @if (loading()) {
        <p role="status">Loading evaluation evidence…</p>
      }
      @if (!loading() && connected && !items().length && !error()) {
        <div class="work-empty">
          <h2>No evaluations recorded</h2>
          <p>
            Run the local evaluation harness and import its verified report.
            Model execution results and synthetic fixtures will be labeled
            separately.
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
                  >{{ item.count }} declared runs · {{ item.status }}</small
                ></span
              ><span class="research-label">{{
                item.source === "synthetic"
                  ? "Synthetic fixture"
                  : item.source === "model"
                    ? "Model results"
                    : item.source === "mixed"
                      ? "Mixed evidence"
                      : "No outcomes yet"
              }}</span
              ><i class="ph ph-arrow-right" aria-hidden="true"></i>
            </button>
          </li>
        }
      </ul>
      @if (next() !== null) {
        <button class="work-secondary" (click)="more()" [disabled]="loading()">
          More evaluations
        </button>
      }
    </section>
    @if (selected(); as data) {
      <veya-panel title="Evaluation evidence" (closed)="close()"
        ><div class="work-panel-content">
          <h2 data-autofocus tabindex="-1">{{ data.title }}</h2>
          <p>
            {{ data.outcomes.length }} of
            {{ data.expected_ids.length }} declared outcomes recorded. Missing
            runs remain in the denominator.
          </p>
          <dl class="work-properties">
            <div>
              <dt>Independent units</dt>
              <dd>{{ data.interval.independent_units }} task families</dd>
            </div>
            <div>
              <dt>Paired difference</dt>
              <dd>{{ percent(data.interval.delta) }}</dd>
            </div>
            <div>
              <dt>95% interval</dt>
              <dd>
                {{ percent(data.interval.low) }} to
                {{ percent(data.interval.high) }} · {{ data.interval.status }}
              </dd>
            </div>
          </dl>
          <table class="research-metrics">
            <caption>
              Quality and resource use by candidate
            </caption>
            <thead>
              <tr>
                <th scope="col">Candidate</th>
                <th scope="col">Success</th>
                <th scope="col">P95</th>
                <th scope="col">Known cost</th>
              </tr>
            </thead>
            <tbody>
              @for (row of summaries(); track row.name) {
                <tr>
                  <th scope="row">{{ row.name }}</th>
                  <td>
                    {{ row.success }} / {{ row.total
                    }}<small>{{ row.missing }} missing</small>
                  </td>
                  <td>{{ row.p95 === null ? "Unknown" : row.p95 + " ms" }}</td>
                  <td>
                    {{ row.cost }} microunits<small
                      >{{ row.unknown }} costs unknown</small
                    >
                  </td>
                </tr>
              }
            </tbody>
          </table>
          <label for="research-family">Task family</label
          ><select
            id="research-family"
            [value]="family()"
            (change)="filter($event)"
          >
            <option value="">All families</option>
            @for (f of families(); track f) {
              <option [value]="f">{{ f }}</option>
            }
          </select>
          <ul class="research-list">
            @for (run of visible(); track run.id) {
              <li>
                <button class="research-row" (click)="detail.set(run)">
                  <span
                    ><strong>{{ run.case_id }}</strong
                    ><small
                      >{{ run.candidate }} · {{ run.status }} ·
                      {{ run.duration_ms }} ms</small
                    ></span
                  ><span>{{
                    run.source === "synthetic"
                      ? "Synthetic fixture"
                      : "Model result"
                  }}</span>
                </button>
              </li>
            }
          </ul>
          @if (detail(); as run) {
            <section class="research-detail" aria-label="Exact run evidence">
              <h3>{{ run.id }}</h3>
              <p>
                {{ run.family }} · repetition {{ run.repetition + 1 }} ·
                {{ run.violations }} policy violations
              </p>
              <p>
                {{ run.tokens === null ? "Unknown" : run.tokens }} tokens · cost
                {{
                  run.cost_microunits === null
                    ? "unknown"
                    : run.cost_microunits + " microunits"
                }}
              </p>
              <h4>Inspected evidence IDs</h4>
              <ul>
                @for (id of run.evidence_ids; track id) {
                  <li>
                    <code>{{ id }}</code>
                  </li>
                }
              </ul>
            </section>
          }
          <p class="work-muted">
            An interval or successful fixture is not automatic production
            approval.
          </p>
          <details>
            <summary>Configuration fingerprint</summary>
            <code class="research-hash">{{ data.spec_hash }}</code>
          </details>
        </div></veya-panel
      >
    }`,
})
export class EvaluationReports implements OnChanges, OnDestroy {
  @Input() connected = false;
  readonly items = signal<Summary[]>([]);
  readonly next = signal<number | null>(null);
  readonly loading = signal(false);
  readonly error = signal("");
  readonly selected = signal<Report | null>(null);
  readonly detail = signal<Outcome | null>(null);
  readonly family = signal("");
  private version = 0;
  ngOnChanges() {
    void this.refresh();
  }
  ngOnDestroy() {
    this.version++;
  }
  async refresh() {
    this.selected.set(null);
    this.detail.set(null);
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
      const data = await listing("evaluations", after);
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
      const data = await report(id);
      if (v === this.version) {
        this.selected.set(data);
        this.family.set("");
        this.detail.set(null);
      }
    } catch (e) {
      if (v === this.version) this.error.set(errorText(e));
    }
  }
  close() {
    this.version++;
    this.selected.set(null);
    this.detail.set(null);
  }
  summaries() {
    const data = this.selected();
    if (!data) return [];
    return [data.baseline, data.candidate].map((name) => {
      const rows = data.outcomes.filter((r) => r.candidate === name),
        total = data.expected_runs.filter((j) => j.candidate === name).length,
        durations = rows.map((r) => r.duration_ms).sort((a, b) => a - b);
      return {
        name,
        total,
        missing: total - rows.length,
        success: rows.filter(
          (r) => r.status === "succeeded" && r.violations === 0,
        ).length,
        p95: durations.length
          ? durations[Math.ceil(durations.length * 0.95) - 1]
          : null,
        cost: rows.reduce((n, r) => n + (r.cost_microunits ?? 0), 0),
        unknown: total - rows.filter((r) => r.cost_microunits !== null).length,
      };
    });
  }
  families() {
    return [
      ...new Set(this.selected()?.outcomes.map((r) => r.family) ?? []),
    ].sort();
  }
  visible() {
    return (
      this.selected()?.outcomes.filter(
        (r) => !this.family() || r.family === this.family(),
      ) ?? []
    );
  }
  filter(e: Event) {
    this.family.set((e.target as HTMLSelectElement).value);
    this.detail.set(null);
  }
  percent(n: number | null) {
    return n === null ? "Not established" : (n * 100).toFixed(1) + "%";
  }
}
