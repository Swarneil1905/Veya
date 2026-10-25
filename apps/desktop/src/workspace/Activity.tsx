import { useEffect, useRef, useState } from 'react';
import { ActivityEvent, errorText, events, latestRun, Task } from './client';

export const stateLabel: Record<string, string> = { queued: 'Queued', running: 'In progress', waiting: 'Waiting', succeeded: 'Completed', failed: 'Failed', cancelled: 'Cancelled' };
function eventText(event: ActivityEvent) {
  if (event.kind === 'run.state_changed' && typeof event.data.to === 'string') return stateLabel[event.data.to] ?? 'State updated';
  if (typeof event.data.message === 'string') return event.data.message.slice(0, 4000);
  return event.kind.replaceAll('.', ' ').replaceAll('_', ' ');
}
export function Activity({ task, connected, initialTab = 'overview', onStateChange }: {
  task: Task; connected: boolean; initialTab?: 'overview' | 'activity'; onStateChange: (id: string, state: string) => void;
}) {
  const [tab, setTab] = useState(initialTab);
  const [rows, setRows] = useState<ActivityEvent[]>([]);
  const [status, setStatus] = useState(task.state);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const heading = useRef<HTMLHeadingElement>(null);
  const position = useRef<{ run: string; cursor: string | null }>({ run: '', cursor: null });
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => {
    if (!connected) { setLoading(false); return; }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      let delay = 1500;
      try {
        const run = await latestRun(task.id);
        if (cancelled) return;
        if (position.current.run !== run.id) {
          position.current = { run: run.id, cursor: null }; setRows([]);
        }
        const page = await events(run.id, position.current.cursor);
        if (cancelled) return;
        position.current.cursor = page.next_cursor;
        setRows(previous => {
          const merged = new Map(previous.map(row => [row.sequence, row]));
          for (const row of page.items) merged.set(row.sequence, row);
          return [...merged.values()].slice(-500);
        });
        setStatus(run.state); onStateChange(task.id, run.state); setError('');
        if (page.has_more) delay = 50;
      } catch (cause) { if (!cancelled) setError(errorText(cause)); }
      finally { if (!cancelled) { setLoading(false); timer = setTimeout(poll, delay); } }
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [task.id, connected, onStateChange]);
  function moveTab(event: React.KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 'overview' : event.key === 'End' ? 'activity' : tab === 'overview' ? 'activity' : 'overview';
    setTab(next); document.getElementById(`task-tab-${next}`)?.focus();
  }
  return <section className="work-activity" aria-labelledby="activity-title">
    <div className="work-detail-heading"><span className="work-task-state" data-state={status}>{stateLabel[status]}</span><h2 id="activity-title" ref={heading} data-autofocus tabIndex={-1}>{task.title}</h2></div>
    <div className="work-detail-tabs" role="tablist" aria-label="Task information">{(['overview', 'activity'] as const).map(item => <button key={item} id={`task-tab-${item}`} role="tab" aria-selected={tab === item} aria-controls={`task-panel-${item}`} tabIndex={tab === item ? 0 : -1} onClick={() => setTab(item)} onKeyDown={moveTab}>{item === 'overview' ? 'Overview' : 'Activity'}</button>)}</div>
    <div className="work-panel-content">
      {status === 'queued' && <p className="work-notice">Saved and queued. AI execution is not connected yet.</p>}
      {!connected && <p role="status">Disconnected. Saved activity will resume when the runtime reconnects.</p>}
      {error && <p className="work-error" role="alert">{error} Activity will reconnect automatically.</p>}
      <div id="task-panel-overview" role="tabpanel" aria-labelledby="task-tab-overview" hidden={tab !== 'overview'} tabIndex={0}>
        <h3>Brief</h3><p className="work-instruction">{task.instruction}</p>
        <dl className="work-properties"><div><dt>Created</dt><dd><time dateTime={task.created_at}>{new Date(task.created_at).toLocaleString()}</time></dd></div><div><dt>Workspace</dt><dd>Personal</dd></div></dl>
        <div className="work-detail-note"><h3>What happens next</h3><p>Your brief is saved. Recorded progress appears in Activity. AI execution and document attachments are not connected yet.</p></div>
      </div>
      <div id="task-panel-activity" role="tabpanel" aria-labelledby="task-tab-activity" hidden={tab !== 'activity'} tabIndex={0}>
        <h3>Recorded activity</h3>
        {loading && <p role="status">Loading activity…</p>}
        {!loading && rows.length === 0 && <p className="work-muted">No execution activity has been recorded.</p>}
        <ol className="work-events" aria-label="Recorded activity">{rows.map(row => <li key={`${row.run_id}:${row.sequence}`}>
          <span className="work-event-marker" aria-hidden="true" /><div><span>{eventText(row)}</span><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time></div>
        </li>)}</ol>
        {rows.length === 500 && <p>Showing the latest 500 events. The complete history remains saved.</p>}
        <p className="work-muted">Partial activity is not a completed result.</p>
      </div>
    </div>
  </section>;
}
