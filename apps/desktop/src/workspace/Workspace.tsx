import { useCallback, useEffect, useRef, useState } from 'react';
import { SidebarSimple } from '@phosphor-icons/react/dist/csr/SidebarSimple';
import { Tray } from '@phosphor-icons/react/dist/csr/Tray';
import { Plus } from '@phosphor-icons/react/dist/csr/Plus';
import { PlugsConnected } from '@phosphor-icons/react/dist/csr/PlugsConnected';
import { Activity } from './Activity';
import { Composer } from './Composer';
import { Panel } from './Panel';
import { TaskList } from './TaskList';
import { errorText, health, Health, isNative, listTasks, recovery, Task } from './client';
import './workspace.css';

function savedNavigation() { try { return localStorage.getItem('veya-navigation-v1') === 'expanded'; } catch { return false; } }

export default function Workspace() {
  const native = isNative();
  const [connection, setConnection] = useState<Health>({ state: native ? 'starting' : 'preview', message: native ? 'Connecting to your local workspace…' : 'Browser preview. Open the desktop app to save work.' });
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [initialTab, setInitialTab] = useState<'overview' | 'activity'>('overview');
  const [composing, setComposing] = useState(false);
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [expanded, setExpanded] = useState(savedNavigation);
  const [readOnly, setReadOnly] = useState(true);
  const [loading, setLoading] = useState(native);
  const [error, setError] = useState('');
  const [restarting, setRestarting] = useState(false);
  const restartLock = useRef(false);
  const refreshVersion = useRef(0);
  const ready = connection.state === 'ready';
  const refresh = useCallback(async () => {
    const version = ++refreshVersion.current;
    setLoading(true); setReadOnly(true);
    try {
      const [items, locked] = await Promise.all([listTasks(), recovery()]);
      if (version !== refreshVersion.current) return;
      setTasks(items); setReadOnly(locked); setError('');
      setSelected(previous => previous ? items.find(item => item.id === previous.id) ?? previous : null);
    } catch (cause) { if (version === refreshVersion.current) { setError(errorText(cause)); setReadOnly(true); } }
    finally { if (version === refreshVersion.current) setLoading(false); }
  }, []);
  useEffect(() => {
    if (!native) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { const value = await health(); if (!cancelled && !restartLock.current) setConnection(value); }
      catch { if (!cancelled && !restartLock.current) setConnection({ state: 'failed', message: 'The runtime connection was interrupted. Restart to reconnect.' }); }
      finally { if (!cancelled) timer = setTimeout(poll, 2000); }
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [native]);
  useEffect(() => {
    if (ready) void refresh(); else { setLoading(false); setReadOnly(true); }
    return () => { refreshVersion.current++; };
  }, [ready, refresh]);
  const updateState = useCallback((id: string, state: string) => {
    setTasks(previous => previous.map(task => task.id === id && task.state !== state ? { ...task, state } : task));
    setSelected(previous => previous?.id === id && previous.state !== state ? { ...previous, state } : previous);
  }, []);
  async function restart() {
    if (restartLock.current) return;
    restartLock.current = true; setRestarting(true); setConnection({ state: 'starting', message: 'Reconnecting to saved work…' });
    try { setConnection(await health(true)); }
    catch (cause) { setConnection({ state: 'failed', message: errorText(cause) }); }
    finally { restartLock.current = false; setRestarting(false); }
  }
  function newTask() { setSelected(null); setComposing(true); }
  function toggleNavigation() {
    const next = !expanded; setExpanded(next);
    try { localStorage.setItem('veya-navigation-v1', next ? 'expanded' : 'collapsed'); } catch { /* Navigation still works without persistence. */ }
  }
  const connectionLabel = ready ? 'Connected' : connection.state === 'preview' ? 'Browser preview' : restarting || connection.state === 'starting' ? 'Connecting' : 'Disconnected';
  return <div className="veya-workspace" data-navigation={expanded ? 'expanded' : 'collapsed'}>
    <a className="work-skip" href="#work-main">Skip to workspace</a>
    <aside className="work-sidebar" aria-label="Workspace navigation">
      <button className="work-nav-toggle" onClick={toggleNavigation} aria-expanded={expanded} aria-controls="work-navigation" aria-label={expanded ? 'Collapse navigation' : 'Expand navigation'} title={expanded ? 'Collapse navigation' : 'Expand navigation'}><SidebarSimple size={21} aria-hidden="true" /><span>Workspace</span></button>
      <nav id="work-navigation" aria-label="Workspace"><button className="work-nav-item" aria-current="page" aria-label="Work" title="Work" onClick={() => { setSelected(null); setComposing(false); document.getElementById('work-heading')?.focus(); }}><Tray size={21} aria-hidden="true" /><span>Work</span></button></nav>
      <button className="work-nav-item work-nav-bottom" onClick={() => setConnectionOpen(true)} aria-label="Connection details" title="Connection details"><PlugsConnected size={21} aria-hidden="true" /><span>Connection</span></button>
    </aside>
    <div className="work-body">
      <header className="work-topbar"><div className="work-brand">Veya<span>Personal workspace</span></div><button className="work-connection-button" onClick={() => setConnectionOpen(true)}><span className="work-connection-dot" data-ready={ready} aria-hidden="true" />{connectionLabel}</button></header>
      <main id="work-main" className="work-main">
        <div className="work-page-heading"><div><h1 id="work-heading" tabIndex={-1}>Work</h1><p>Your briefs, progress, and next steps.</p></div><button className="work-primary" onClick={newTask}><Plus size={18} aria-hidden="true" />New task</button></div>
        {!ready && <div className="work-connection-notice" role="status"><span>{connection.message}</span>{native && <button className="work-link" onClick={() => setConnectionOpen(true)}>Connection details</button>}</div>}
        {ready && readOnly && !error && <p className="work-notice" role="status">{loading ? 'Checking saved work before enabling task saving…' : 'This workspace is read-only pending recovery review.'}</p>}
        <TaskList tasks={tasks} loading={loading} connected={ready} error={error} onRefresh={() => void refresh()} onNew={newTask} onSelect={task => { setInitialTab('overview'); setSelected(task); }} />
      </main>
    </div>
    <Panel open={composing} title="New task" onClose={() => setComposing(false)}>
      <div className="work-panel-content"><h2>A clear brief. A place to start.</h2><p className="work-intro">Describe the work and what a useful result should include.</p>
        <Composer enabled={ready && !readOnly} onCreated={task => { setComposing(false); setInitialTab('activity'); setSelected(task); setTasks(previous => [task, ...previous.filter(item => item.id !== task.id)].slice(0, 10)); void refresh(); }} />
      </div>
    </Panel>
    <Panel open={selected !== null} title="Task details" onClose={() => setSelected(null)}>
      {selected && <Activity key={selected.id} task={selected} connected={ready} initialTab={initialTab} onStateChange={updateState} />}
    </Panel>
    <Panel open={connectionOpen} title="Connection" kind="connection" onClose={() => setConnectionOpen(false)}>
      <div className="work-panel-content"><h2 data-autofocus tabIndex={-1}>{connectionLabel}</h2><p role="status">{connection.message}</p><dl className="work-properties"><div><dt>Workspace</dt><dd>Personal</dd></div><div><dt>Storage</dt><dd>On this device</dd></div></dl>
        {native && <button className="work-primary" disabled={restarting} onClick={() => void restart()}>{restarting ? 'Restarting…' : 'Restart runtime'}</button>}
        <p className="work-muted">Task saving and recorded activity are available in the desktop app. AI execution and document attachments are not connected yet.</p>
      </div>
    </Panel>
  </div>;
}
