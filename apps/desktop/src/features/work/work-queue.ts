export type QueueQuery = { search: string; status: string; sort: 'newest' | 'oldest' };
export const defaultQuery: QueueQuery = {search:'',status:'all',sort:'newest'};
const key = 'veya-work-queue-v1';
export function loadQueue(): {query: QueueQuery; selected: string | null} {
  try {
    const value = JSON.parse(localStorage.getItem(key) || 'null');
    if (value && typeof value.query?.search === 'string' && value.query.search.length <= 200 &&
        ['all','active','attention','completed'].includes(value.query.status) && ['newest','oldest'].includes(value.query.sort)) {
      return {query:value.query,selected:typeof value.selected === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(value.selected) ? value.selected : null};
    }
  } catch { /* Corrupt or unavailable preferences do not prevent access to work. */ }
  return {query:{...defaultQuery},selected:null};
}
export function saveQueue(query: QueueQuery, selected: string | null) {
  try {localStorage.setItem(key, JSON.stringify({query,selected}));} catch { /* Storage may be disabled. */ }
}
