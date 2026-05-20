import { normalizeStoredSuggestion, type SuggestionChip } from './suggestions';

// Browser localStorage adapter; `getStorage()` returns null on RN/SSR so callers no-op gracefully off-web.
export function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage ?? null;
}

// Storage keys are internal identifiers, not user-facing labels; they don't move with locale.
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

const SUGGESTIONS_PREFIX = 'trpg.suggestions.';

export function loadSuggestions(gameId: string): SuggestionChip[] {
  const raw = getStorage()?.getItem(`${SUGGESTIONS_PREFIX}${gameId}`);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.flatMap((item) => {
          const normalized = normalizeStoredSuggestion(item);
          return normalized ? [normalized] : [];
        })
      : [];
  } catch {
    return [];
  }
}

export function storeSuggestions(gameId: string, suggestions: SuggestionChip[]): void {
  if (suggestions.length === 0) {
    getStorage()?.removeItem(`${SUGGESTIONS_PREFIX}${gameId}`);
    return;
  }
  getStorage()?.setItem(`${SUGGESTIONS_PREFIX}${gameId}`, JSON.stringify(suggestions));
}

// Clear all per-game UI caches on new-game (avoids stale data leaking to next playthrough).
export function clearAllForGame(gameId: string): void {
  const s = getStorage();
  if (!s) return;
  s.removeItem(`${SUGGESTIONS_PREFIX}${gameId}`);
}
