import { Component, Output, EventEmitter, signal } from "@angular/core";
import { Panel } from "../../workspace/panel";
export type Destination = "work" | "new" | "approvals" | "connection";
@Component({
  selector: "veya-commands",
  imports: [Panel],
  template: `<veya-panel
    title="Commands"
    kind="connection"
    (closed)="closed.emit()"
    ><div class="work-panel-content">
      <h2>Go to or create</h2>
      <label for="command-search">Find a command</label
      ><input
        id="command-search"
        type="search"
        autocomplete="off"
        data-autofocus
        [value]="query()"
        (input)="search($event)"
        (keydown)="navigate($event)"
      />
      <ul class="work-command-list">
        @for (item of filtered(); track item.id) {
          <li>
            <button
              type="button"
              class="work-secondary"
              (click)="chosen.emit(item.id)"
            >
              <i [class]="'ph ' + item.icon" aria-hidden="true"></i
              >{{ item.label }}
            </button>
          </li>
        }
      </ul>
      @if (!filtered().length) {
        <p role="status">No matching commands.</p>
      }
      <p class="work-muted">
        Tab to a command. Enter to open. Escape to return.
      </p>
    </div></veya-panel
  >`,
})
export class Commands {
  @Output() chosen = new EventEmitter<Destination>();
  @Output() closed = new EventEmitter<void>();
  readonly query = signal("");
  readonly actions: { id: Destination; label: string; icon: string }[] = [
    { id: "new", label: "New task", icon: "ph-plus" },
    { id: "work", label: "Work inbox", icon: "ph-tray" },
    { id: "approvals", label: "Approvals", icon: "ph-check-square" },
    {
      id: "connection",
      label: "Connection details",
      icon: "ph-plugs-connected",
    },
  ];
  filtered() {
    return this.actions.filter((v) =>
      v.label.toLowerCase().includes(this.query().toLowerCase()),
    );
  }
  search(event: Event) {
    this.query.set((event.target as HTMLInputElement).value);
  }
  navigate(event: KeyboardEvent) {
    if (event.key === "Enter" && this.filtered().length === 1) {
      event.preventDefault();
      this.chosen.emit(this.filtered()[0].id);
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      document
        .querySelector<HTMLButtonElement>(".work-command-list button")
        ?.focus();
    }
  }
}
