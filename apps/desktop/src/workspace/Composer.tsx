import { useRef, useState } from 'react';
import { Draft, errorText, submit, Task } from './client';

const KEY = 'veya-task-draft-v1';
function empty(): Draft { return { client_request_id: crypto.randomUUID(), title: '', instruction: '', attempted: false }; }
function readDraft(): Draft {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) ?? 'null');
    if (value && typeof value.client_request_id === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(value.client_request_id) &&
        typeof value.title === 'string' && typeof value.instruction === 'string' && typeof value.attempted === 'boolean') return value;
  } catch { /* An unreadable draft never turns into a submitted task. */ }
  return empty();
}

export function Composer({ enabled, onCreated }: { enabled: boolean; onCreated: (task: Task) => void }) {
  const [draft, setDraft] = useState(readDraft);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const sending = useRef(false);
  function save(next: Draft) {
    setDraft(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); return true; }
    catch { setError('Your draft could not be saved on this device. Free storage or allow local storage before submitting.'); return false; }
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!enabled || sending.current || !draft.title.trim() || !draft.instruction.trim()) return;
    const request = { ...draft, title: draft.title.trim(), instruction: draft.instruction.trim(), attempted: true };
    if (!save(request)) return;
    sending.current = true; setPending(true); setError('');
    try {
      const result = await submit(request);
      save(empty()); onCreated(result.task);
    } catch (cause) {
      // Validation rejection is definitive: no task was created. Ambiguous failures
      // retain the immutable request, but invalid input must remain correctable.
      if ((cause instanceof Error ? cause.message : String(cause)) === 'invalid_input') {
        save({ ...request, attempted: false });
      }
      setError(errorText(cause));
    }
    finally { sending.current = false; setPending(false); }
  }
  return <form className="work-composer" onSubmit={send} aria-busy={pending}>
    <label htmlFor="task-title">Task name</label>
    <input id="task-title" name="title" autoComplete="off" data-autofocus maxLength={200} required value={draft.title} readOnly={draft.attempted}
      onChange={e => save({ ...draft, title: e.target.value })} placeholder="For example, review the supplier order" />
    <label htmlFor="task-instruction">What would you like done?</label>
    <textarea id="task-instruction" name="instruction" autoComplete="off" maxLength={20000} required rows={8} value={draft.instruction} readOnly={draft.attempted}
      onChange={e => save({ ...draft, instruction: e.target.value })} placeholder="Describe the task and what a useful result should include." />
    <div className="work-submit"><p>Tasks are saved locally. AI execution and attachments are coming next.</p>
      <button className="work-primary" disabled={!enabled || pending || !draft.title.trim() || !draft.instruction.trim()}>
        {pending ? 'Saving task…' : draft.attempted ? 'Retry same task' : 'Save task'}</button></div>
    {draft.attempted && !pending && <p className="work-muted">We could not confirm whether this task was saved. Retry checks the same submission. Your original brief is kept intact to avoid duplicates.</p>}
    {error && <p className="work-error" role="alert">{error}</p>}
  </form>;
}
