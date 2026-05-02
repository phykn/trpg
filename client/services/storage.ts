// Browser localStorage adapter; `getStorage()` returns null on RN/SSR so callers no-op gracefully off-web.
export function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage ?? null;
}

const CURRENT_GAME_KEY = 'trpg.current_game_id';

export function loadStoredGameId(): string | null {
  return getStorage()?.getItem(CURRENT_GAME_KEY) ?? null;
}

export function storeGameId(gameId: string): void {
  getStorage()?.setItem(CURRENT_GAME_KEY, gameId);
}

export function clearStoredGameId(): void {
  getStorage()?.removeItem(CURRENT_GAME_KEY);
}
