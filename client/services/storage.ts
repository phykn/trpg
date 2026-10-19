const KEY = 'trpg.game_id';

export function loadGameId(): string | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function storeGameId(id: string): boolean {
  try {
    if (typeof window === 'undefined') return false;
    window.localStorage.setItem(KEY, id);
    return true;
  } catch {
    return false;
  }
}

export function clearGameId(): void {
  try {
    if (typeof window !== 'undefined') window.localStorage.removeItem(KEY);
  } catch { /* storage unavailable: nothing to clear */ }
}

const LOG = 'trpg.log.';

// The chat history is a per-device convenience: losing it never changes the game.
export function loadLog<T>(id: string): T[] {
  try {
    const raw = typeof window === 'undefined' ? null : window.localStorage.getItem(LOG + id);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function storeLog<T>(id: string, entries: T[]): void {
  try {
    if (typeof window === 'undefined') return;
    const store = window.localStorage;
    for (let i = store.length - 1; i >= 0; i -= 1) {
      const k = store.key(i);
      if (k?.startsWith(LOG) && k !== LOG + id) store.removeItem(k);    // only the saved game keeps a history
    }
    store.setItem(LOG + id, JSON.stringify(entries));
  } catch { /* storage full or unavailable: the history stays in memory */ }
}
