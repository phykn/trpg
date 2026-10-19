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
