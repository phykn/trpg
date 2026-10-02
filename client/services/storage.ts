const KEY = 'trpg.adventure_game_id';

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
