import { useRef, useState } from 'react';
import { MagnifyingGlass } from '@phosphor-icons/react/dist/csr/MagnifyingGlass';
import { ArrowClockwise } from '@phosphor-icons/react/dist/csr/ArrowClockwise';
import { Task } from './client';
import { stateLabel } from './Activity';

const filters = [
  { id: 'all', label: 'All work', matches: (_task: Task) => true },
  { id: 'active', label: 'Active', matches: (task: Task) => ['queued', 'running'].includes(task.state) },
  { id: 'attention', label: 'Needs attention', matches: (task: Task) => ['waiting', 'failed'].includes(task.state) },
  { id: 'completed', label: 'Completed', matches: (task: Task) => task.state === 'succeeded' },
] as const;

export function taskDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function TaskList({ tasks, loading, connected, error, onRefresh, onSelect, onNew }: {
  tasks: Task[]; loading: boolean; connected: boolean; error: string;
  onRefresh: () => void; onSelect: (task: Task) => void; onNew: () => void;
}) {
  const [filter, setFilter] = useState('all');
  const [query, setQuery] = useState('');
  const search = useRef<HTMLInputElement>(null);
  const active = filters.find(item => item.id === filter) ?? filters[0];
  const needle = query.trim().toLocaleLowerCase();
  const visible = tasks.filter(task => active.matches(task) && `${task.title} ${task.instruction}`.toLocaleLowerCase().includes(needle));
  return <section className="work-list" aria-label="Recent work" aria-busy={loading}>
    <div className="work-filters" role="group" aria-label="Filter work">{filters.map(item =>
      <button type="button" key={item.id} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}<span>{tasks.filter(item.matches).length}</span></button>
    )}</div>
    <div className="work-list-tools">
      <label className="work-search"><MagnifyingGlass size={18} aria-hidden="true" /><span className="work-sr-only">Search recent work</span>
        <input ref={search} type="search" autoComplete="off" placeholder="Search recent work…" value={query} onChange={event => setQuery(event.target.value)} />
      </label>
      <button type="button" className="work-secondary" onClick={onRefresh} disabled={!connected || loading}><ArrowClockwise size={16} aria-hidden="true" />{loading ? 'Refreshing…' : 'Refresh'}</button>
    </div>
    {error && <p className="work-error" role="alert">{error} Refresh to try again.</p>}
    {loading && tasks.length === 0 ? <p className="work-empty" role="status">Loading saved work…</p> : visible.length > 0 ?
      <div className="work-table-wrap"><table className="work-table"><caption className="work-sr-only">Saved tasks, newest first</caption>
        <thead><tr><th scope="col">Task</th><th scope="col">Status</th><th scope="col">Created</th></tr></thead>
        <tbody>{visible.map(task => <tr key={task.id}>
          <td><button className="work-task-link" onClick={() => onSelect(task)} aria-label={`Open task: ${task.title}`}><span>{task.title}</span><small>{task.instruction}</small></button></td>
          <td><span className="work-task-state" data-state={task.state}>{stateLabel[task.state]}</span></td>
          <td><time dateTime={task.created_at}>{taskDate(task.created_at)}</time></td>
        </tr>)}</tbody>
      </table></div> : <div className="work-empty" role="status">
        <h2>{tasks.length || needle || filter !== 'all' ? 'No matching work' : 'Your work starts here'}</h2>
        <p>{tasks.length || needle || filter !== 'all' ? 'Try a different search or view.' : 'Give a task a clear brief. Keep its instructions and progress together, from the first note onward.'}</p>
        {tasks.length || needle || filter !== 'all' ? <button className="work-secondary" onClick={() => { setQuery(''); setFilter('all'); search.current?.focus(); }}>Clear filters</button> : <button className="work-secondary" onClick={onNew}>Create your first task</button>}
      </div>}
    <footer className="work-list-footer"><span aria-live="polite">{visible.length} {visible.length === 1 ? 'task' : 'tasks'}{tasks.length === 10 ? ' · Latest 10 saved tasks' : ''}</span><span>Saved on this device</span></footer>
  </section>;
}
