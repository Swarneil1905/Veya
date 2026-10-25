import { Commands, Destination } from "../features/accessibility/commands";
import { HostListener } from "@angular/core";
import { ApprovalReview } from "../features/approvals/approval-review";
import { loadQueue, saveQueue, QueueQuery } from "../features/work/work-queue";
import { Component, OnDestroy, OnInit, signal } from "@angular/core";
import { Activity } from "./activity";
import { Composer } from "./composer";
import { Panel } from "./panel";
import { TaskList } from "./task-list";
import {
  connectWeb,
  errorText,
  health,
  Health,
  isNative,
  isWeb,
  listTasks,
  getTask,
  recovery,
  Task,
} from "./client";

function savedNavigation() {
  try {
    return localStorage.getItem("veya-navigation-v1") === "expanded";
  } catch {
    return false;
  }
}

@Component({
  selector: "veya-workspace",
  imports: [Activity, Composer, Panel, TaskList, ApprovalReview, Commands],
  templateUrl: "./workspace.html",
})
export class Workspace implements OnInit, OnDestroy {
  readonly commandsOpen = signal(false);
  @HostListener("document:keydown", ["$event"]) shortcut(event: KeyboardEvent) {
    if (
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      event.key.toLowerCase() === "k"
    ) {
      event.preventDefault();
      this.commandsOpen.update((v) => !v);
    }
  }
  command(destination: Destination) {
    this.commandsOpen.set(false);
    this.connectionOpen.set(false);
    this.composing.set(false);
    this.closeTask();
    if (destination === "new") this.newTask();
    else if (destination === "connection") this.connectionOpen.set(true);
    else this.view.set(destination);
  }

  readonly view = signal<"work" | "approvals">("work");
  readonly native = isNative();
  readonly web = isWeb();
  readonly connection = signal<Health>({
    state: this.native || this.web ? "starting" : "preview",
    message:
      this.native || this.web
        ? "Connecting to your local workspace…"
        : "Browser preview. Start the Veya web workspace or desktop app to save work.",
  });
  readonly tasks = signal<Task[]>([]);
  readonly selected = signal<Task | null>(null);
  initialTab: "overview" | "activity" = "overview";
  readonly composing = signal(false);
  readonly connectionOpen = signal(false);
  readonly expanded = signal(savedNavigation());
  readonly readOnly = signal(true);
  readonly loading = signal(this.native || this.web);
  readonly error = signal("");
  readonly recoveryMessage = signal("");
  readonly restarting = signal(false);
  readonly query = signal<QueueQuery>(loadQueue().query);
  readonly nextCursor = signal<string | null>(null);
  readonly cursors = signal<(string | null)[]>([null]);
  private restoreSelection = loadQueue().selected;
  private refreshVersion = 0;
  changeQuery(query: QueueQuery) {
    this.query.set(query);
    this.cursors.set([null]);
    this.persistQueue();
    void this.refresh();
  }
  page(direction: "next" | "previous") {
    if (direction === "next" && this.nextCursor())
      this.cursors.update((v) => [...v, this.nextCursor()]);
    if (direction === "previous" && this.cursors().length > 1)
      this.cursors.update((v) => v.slice(0, -1));
    void this.refresh();
  }
  private persistQueue() {
    saveQueue(this.query(), this.selected()?.id ?? null);
  }
  closeTask() {
    this.selected.set(null);
    this.restoreSelection = null;
    this.persistQueue();
  }

  private destroyed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  // Reopening a launcher link in this same tab is a fragment navigation, not a
  // document load. Rebootstrap to exchange the new credential and clear stale UI.
  private readonly reconnectLink = () => {
    if (this.web && new URLSearchParams(location.hash.slice(1)).has("session"))
      location.reload();
  };
  ready() {
    return this.connection().state === "ready";
  }
  connectionLabel() {
    return this.ready()
      ? "Connected"
      : this.connection().state === "preview"
        ? "Browser preview"
        : this.connection().state === "starting"
          ? "Connecting"
          : "Disconnected";
  }
  async ngOnInit() {
    window.addEventListener("hashchange", this.reconnectLink);
    if (this.web) await connectWeb();
    if (!this.destroyed && (this.native || this.web)) void this.poll();
  }
  ngOnDestroy() {
    this.destroyed = true;
    this.refreshVersion++;
    clearTimeout(this.timer);
    window.removeEventListener("hashchange", this.reconnectLink);
  }
  private setConnection(value: Health) {
    const wasReady = this.ready();
    this.connection.set(value);
    if (!this.ready()) {
      this.refreshVersion++;
      this.loading.set(false);
      this.readOnly.set(true);
    } else if (!wasReady) void this.refresh();
  }
  private async poll() {
    try {
      const value = await health();
      if (!this.destroyed && !this.restarting()) this.setConnection(value);
    } catch {
      if (!this.destroyed && !this.restarting())
        this.setConnection({
          state: "failed",
          message: this.web
            ? "Open the connection link from the local web launcher to reconnect."
            : "The runtime connection was interrupted. Restart to reconnect.",
        });
    } finally {
      if (!this.destroyed)
        this.timer = setTimeout(() => void this.poll(), 2000);
    }
  }
  async refresh() {
    const version = ++this.refreshVersion;
    this.loading.set(true);
    this.readOnly.set(true);
    try {
      const [firstPage, locked] = await Promise.all([
        listTasks(this.query(), this.cursors().at(-1) ?? null),
        recovery(),
      ]);
      let page = firstPage;
      if (version !== this.refreshVersion) return;
      if (!page.items.length && this.cursors().length > 1) {
        this.cursors.set([null]);
        page = await listTasks(this.query(), null);
      }
      const items = page.items;
      if (version !== this.refreshVersion) return;
      this.tasks.set(items);
      this.nextCursor.set(page.next_cursor);
      this.readOnly.set(locked.required);
      this.recoveryMessage.set(locked.message);
      this.error.set("");
      const restore = this.restoreSelection;
      this.restoreSelection = null;
      if (restore) {
        try {
          const restored =
            items.find((t) => t.id === restore) ?? (await getTask(restore));
          if (version === this.refreshVersion) this.selected.set(restored);
        } catch {
          /* Deleted selections stay closed. */
        }
      }
      const selected = this.selected();
      if (selected)
        this.selected.set(
          items.find((item) => item.id === selected.id) ?? selected,
        );
    } catch (cause) {
      if (version === this.refreshVersion) {
        if (
          cause instanceof Error &&
          cause.message === "invalid_cursor" &&
          this.cursors().length > 1
        ) {
          this.cursors.set([null]);
          void this.refresh();
          return;
        }
        this.error.set(errorText(cause));
        this.readOnly.set(true);
      }
    } finally {
      if (version === this.refreshVersion) this.loading.set(false);
    }
  }
  async restart() {
    if (this.restarting()) return;
    this.restarting.set(true);
    this.setConnection({
      state: "starting",
      message: "Reconnecting to saved work…",
    });
    try {
      this.setConnection(await health(true));
    } catch (cause) {
      this.setConnection({ state: "failed", message: errorText(cause) });
    } finally {
      this.restarting.set(false);
    }
  }
  updateState({ id, state }: { id: string; state: string }) {
    const changed = this.tasks().some((t) => t.id === id && t.state !== state);
    this.tasks.update((items) =>
      items.map((t) =>
        t.id === id && t.state !== state ? { ...t, state } : t,
      ),
    );
    this.selected.update((t) =>
      t?.id === id && t.state !== state ? { ...t, state } : t,
    );
    if (changed) void this.refresh();
  }
  newTask() {
    this.closeTask();
    this.composing.set(true);
  }
  openTask(task: Task) {
    this.initialTab = "overview";
    this.selected.set(task);
    this.persistQueue();
  }
  created(task: Task) {
    this.composing.set(false);
    this.initialTab = "activity";
    this.selected.set(task);
    this.persistQueue();
    this.tasks.update((items) =>
      [task, ...items.filter((t) => t.id !== task.id)].slice(0, 10),
    );
    void this.refresh();
  }
  work() {
    this.view.set("work");
    this.closeTask();
    this.composing.set(false);
    document.getElementById("work-heading")?.focus();
  }
  toggleNavigation() {
    const next = !this.expanded();
    this.expanded.set(next);
    try {
      localStorage.setItem(
        "veya-navigation-v1",
        next ? "expanded" : "collapsed",
      );
    } catch {
      /* Optional preference only. */
    }
  }
}
