import type { Task as ContractTask } from '../../../../packages/contracts/src/index';
import type { QueueQuery } from '../features/work/work-queue';
export type Health = { state: string; message: string };
export type Task = Required<Pick<ContractTask, 'id' | 'title' | 'instruction' | 'state' | 'created_at'>>;
export type Run = { id: string; state: string };
export type ActivityEvent = { run_id: string; sequence: number; kind: string; data: Record<string, unknown>; created_at: string };
export type EventPage = { items: ActivityEvent[]; next_cursor: string | null; has_more: boolean };
export type Draft = { client_request_id: string; title: string; instruction: string; attempted: boolean };

declare global { interface Window { __TAURI__?: { core: { invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown> } } } }
export const isNative = () => Boolean(window.__TAURI__?.core);
export const isWeb = () => document.querySelector('meta[name="veya-platform"]')?.getAttribute('content') === 'local';
export async function connectWeb() {
  const token = new URLSearchParams(location.hash.slice(1)).get('session');
  if (!token) return;
  // Remove the bootstrap credential before loading any task content. The cookie
  // is HttpOnly; neither the worker credential nor a bearer is stored by the UI.
  history.replaceState(null, '', location.pathname);
  try { await fetch('/api/session', {method:'POST',headers:{Authorization:`Bearer ${token}`},credentials:'same-origin'}); }
  catch { /* Health polling presents the reconnect state. */ }
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_response');
  return value as Record<string, unknown>;
}
function string(value: unknown): string {
  if (typeof value !== 'string') throw new Error('invalid_response');
  return value;
}
const states = new Set(['queued', 'running', 'waiting', 'succeeded', 'failed', 'cancelled']);
function state(value: unknown) { const text = string(value); if (!states.has(text)) throw new Error('invalid_response'); return text; }
function task(value: unknown): Task {
  const v = object(value);
  return { id: string(v.id), title: string(v.title), instruction: string(v.instruction), state: state(v.state), created_at: string(v.created_at) };
}
function run(value: unknown): Run { const v = object(value); return { id: string(v.id), state: state(v.state) }; }
async function invoke(command: string, args?: Record<string, unknown>) {
  if (window.__TAURI__?.core) return window.__TAURI__.core.invoke(command, args);
  if (!isWeb()) throw new Error('desktop_required');
  if (command === 'runtime_restart') throw new Error('forbidden');
  const response = await fetch(command === 'runtime_health' ? '/api/health' : '/api/workspace', {
    method: command === 'runtime_health' ? 'GET' : 'POST', credentials:'same-origin',
    headers: {'Content-Type':'application/json'}, body: command === 'runtime_health' ? undefined : JSON.stringify(args),
    signal: AbortSignal.timeout(12000),
  });
  const value = object(await response.json());
  if (!response.ok) throw new Error(string(object(value['error'])['code']));
  if (command === 'runtime_health') {
    if (value['protocol'] !== 1) throw new Error('invalid_response');
    return {state:'ready',message:'Connected to your local workspace.'};
  }
  return value;
}
export async function call(operation: string, args: Record<string, unknown> = {}) { return invoke('workspace_call', { operation, args }); }
export async function health(restart = false): Promise<Health> {
  const v = object(await invoke(restart ? 'runtime_restart' : 'runtime_health'));
  return { state: string(v.state), message: string(v.message) };
}
export async function listTasks(query: QueueQuery, cursor: string | null): Promise<{items: Task[]; next_cursor: string | null}> {
  const v = object(await call('list_tasks', {search:query.search, sort:query.sort, ...(query.status === 'all' ? {} : {status:query.status}), cursor}));
  if (!Array.isArray(v.items) || !(v.next_cursor === null || typeof v.next_cursor === 'string')) throw new Error('invalid_response');
  return {items:v.items.map(task),next_cursor:v.next_cursor};
}
export async function getTask(id: string): Promise<Task> { return task(await call('get_task', {task_id:id})); }
export async function recovery(): Promise<{required:boolean; message:string}> {
  const v = object(await call('recovery'));
  if (typeof v.required !== 'boolean') throw new Error('invalid_response');
  return {required:v.required, message:typeof v['message']==='string'?v['message']:''};
}
export async function submit(draft: Draft): Promise<{ task: Task; run: Run }> {
  const { client_request_id, title, instruction } = draft;
  const v = object(await call('submit_task', { client_request_id, title, instruction }));
  return { task: task(v.task), run: run(v.run) };
}
export async function latestRun(taskId: string): Promise<Run> { return run(await call('latest_run', { task_id: taskId })); }
export async function events(runId: string, after: string | null): Promise<EventPage> {
  const v = object(await call('events', { run_id: runId, after }));
  if (!Array.isArray(v.items) || typeof v.has_more !== 'boolean' || !(v.next_cursor === null || typeof v.next_cursor === 'string')) throw new Error('invalid_response');
  let position = after === null ? 0 : Number(after.split(':')[1]);
  const items = v.items.map(item => {
    const row = object(item);
    if (row.run_id !== runId || !Number.isSafeInteger(row.sequence) || Number(row.sequence) <= position) throw new Error('invalid_response');
    position = Number(row.sequence);
    return { run_id: runId, sequence: position, kind: string(row.kind), data: object(row.data), created_at: string(row.created_at) };
  });
  const expected = items.length ? `${runId}:${position}` : after;
  if (v.next_cursor !== expected || (v.has_more && !items.length)) throw new Error('invalid_response');
  return { items, next_cursor: expected, has_more: v.has_more };
}
export function errorText(error: unknown): string {
  const code = error instanceof Error ? error.message : String(error);
  const messages: Record<string, string> = {
    desktop_required: 'Open the Veya desktop app to connect to your workspace.',
    forbidden: 'This operation is not permitted.', unauthenticated: 'The connection expired. Restart the runtime.',
    recovery_required: 'This restored workspace is read-only until recovery is reviewed.',
    busy: 'The runtime is busy. Please try again.', conflict: 'This request conflicts with saved work. Check recent work before starting another task.',
    invalid_input: 'The request could not be accepted. Check its title and instruction.',
    invalid_response: 'The runtime returned an unexpected response. Restart it to reconnect.',
  };
  return messages[code] ?? 'The connection was interrupted. Your draft is retained; retry to check the same task.';
}
