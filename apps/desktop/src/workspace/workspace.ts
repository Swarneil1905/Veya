import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { Activity } from './activity';
import { Composer } from './composer';
import { Panel } from './panel';
import { TaskList } from './task-list';
import {
  connectWeb,
  errorText,
  health,
  Health,
  isNative,
  isWeb,
  listTasks,
  recovery,
  Task,
} from './client';

function savedNavigation() {
  try {
    return localStorage.getItem('veya-navigation-v1') === 'expanded';
  } catch {
    return false;
  }
}

@Component({
  selector: 'veya-workspace',
  imports: [Activity, Composer, Panel, TaskList],
  templateUrl: './workspace.html',
})
export class Workspace implements OnInit, OnDestroy {
  readonly native = isNative();
  readonly web = isWeb();
  readonly connection = signal<Health>({
    state: this.native || this.web ? 'starting' : 'preview',
    message:
      this.native || this.web
        ? 'Connecting to your local workspace…'
        : 'Browser preview. Start the Veya web workspace or desktop app to save work.',
  });
  readonly tasks = signal<Task[]>([]);
  readonly selected = signal<Task | null>(null);
  initialTab: 'overview' | 'activity' = 'overview';
  readonly composing = signal(false);
  readonly connectionOpen = signal(false);
  readonly expanded = signal(savedNavigation());
  readonly readOnly = signal(true);
  readonly loading = signal(this.native || this.web);
  readonly error = signal('');
  readonly restarting = signal(false);
  private refreshVersion = 0;
  private destroyed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  // Reopening a launcher link in this same tab is a fragment navigation, not a
  // document load. Rebootstrap to exchange the new credential and clear stale UI.
  private readonly reconnectLink = () => {
    if (this.web && new URLSearchParams(location.hash.slice(1)).has('session')) location.reload();
  };
  ready() {
    return this.connection().state === 'ready';
  }
  connectionLabel() {
    return this.ready()
      ? 'Connected'
      : this.connection().state === 'preview'
        ? 'Browser preview'
        : this.connection().state === 'starting'
          ? 'Connecting'
          : 'Disconnected';
  }
  async ngOnInit() {
    window.addEventListener('hashchange', this.reconnectLink);
    if (this.web) await connectWeb();
    if (!this.destroyed && (this.native || this.web)) void this.poll();
  }
  ngOnDestroy() {
    this.destroyed = true;
    this.refreshVersion++;
    clearTimeout(this.timer);
    window.removeEventListener('hashchange', this.reconnectLink);
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
          state: 'failed',
          message: this.web
            ? 'Open the connection link from the local web launcher to reconnect.'
            : 'The runtime connection was interrupted. Restart to reconnect.',
        });
    } finally {
      if (!this.destroyed) this.timer = setTimeout(() => void this.poll(), 2000);
    }
  }
  async refresh() {
    const version = ++this.refreshVersion;
    this.loading.set(true);
    this.readOnly.set(true);
    try {
      const [items, locked] = await Promise.all([listTasks(), recovery()]);
      if (version !== this.refreshVersion) return;
      this.tasks.set(items);
      this.readOnly.set(locked);
      this.error.set('');
      const selected = this.selected();
      if (selected) this.selected.set(items.find((item) => item.id === selected.id) ?? selected);
    } catch (cause) {
      if (version === this.refreshVersion) {
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
    this.setConnection({ state: 'starting', message: 'Reconnecting to saved work…' });
    try {
      this.setConnection(await health(true));
    } catch (cause) {
      this.setConnection({ state: 'failed', message: errorText(cause) });
    } finally {
      this.restarting.set(false);
    }
  }
  updateState({ id, state }: { id: string; state: string }) {
    this.tasks.update((items) =>
      items.map((t) => (t.id === id && t.state !== state ? { ...t, state } : t)),
    );
    this.selected.update((t) => (t?.id === id && t.state !== state ? { ...t, state } : t));
  }
  newTask() {
    this.selected.set(null);
    this.composing.set(true);
  }
  openTask(task: Task) {
    this.initialTab = 'overview';
    this.selected.set(task);
  }
  created(task: Task) {
    this.composing.set(false);
    this.initialTab = 'activity';
    this.selected.set(task);
    this.tasks.update((items) => [task, ...items.filter((t) => t.id !== task.id)].slice(0, 10));
    void this.refresh();
  }
  work() {
    this.selected.set(null);
    this.composing.set(false);
    document.getElementById('work-heading')?.focus();
  }
  toggleNavigation() {
    const next = !this.expanded();
    this.expanded.set(next);
    try {
      localStorage.setItem('veya-navigation-v1', next ? 'expanded' : 'collapsed');
    } catch {
      /* Optional preference only. */
    }
  }
}
