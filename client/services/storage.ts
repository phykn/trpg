// Browser localStorage adapter and the keys that read/write through it.
// `getStorage()` returns null on RN/SSR (no `window`), so callers no-op
// gracefully off-web. Each browser owns its own active-game pointer — the
// server has no per-user "last game" notion, so two browsers don't fight.

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
