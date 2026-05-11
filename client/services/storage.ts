import { normalizeStoredSuggestion, type SuggestionChip } from './suggestions';

// Browser localStorage adapter; `getStorage()` returns null on RN/SSR so callers no-op gracefully off-web.
export function getStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage ?? null;
}

// Storage keys are internal identifiers, not user-facing labels; they don't move with locale.
const CURRENT_GAME_KEY = 'trpg.current_game_id';
const STORY_GRAPH_PREFIX = 'trpg.story_graph.';

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
const LAST_SEEN_LOCATION_PREFIX = 'trpg.last_seen_location.';
const LAST_SEEN_QUEST_TITLE_PREFIX = 'trpg.last_seen_quest_title.';
const LAST_SEEN_SUBJECT_ID_PREFIX = 'trpg.last_seen_subject_id.';
const SEEN_NODES_PREFIX = 'trpg.seen_nodes.';

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

export function loadLastSeenLocation(gameId: string): string | null {
  return getStorage()?.getItem(`${LAST_SEEN_LOCATION_PREFIX}${gameId}`) ?? null;
}

export function storeLastSeenLocation(gameId: string, locationId: string): void {
  getStorage()?.setItem(`${LAST_SEEN_LOCATION_PREFIX}${gameId}`, locationId);
}

export function loadLastSeenQuestTitle(gameId: string): string | null {
  return getStorage()?.getItem(`${LAST_SEEN_QUEST_TITLE_PREFIX}${gameId}`) ?? null;
}

export function storeLastSeenQuestTitle(gameId: string, title: string): void {
  getStorage()?.setItem(`${LAST_SEEN_QUEST_TITLE_PREFIX}${gameId}`, title);
}

export function loadLastSeenSubjectId(gameId: string): string | null {
  return getStorage()?.getItem(`${LAST_SEEN_SUBJECT_ID_PREFIX}${gameId}`) ?? null;
}

export function storeLastSeenSubjectId(gameId: string, name: string): void {
  getStorage()?.setItem(`${LAST_SEEN_SUBJECT_ID_PREFIX}${gameId}`, name);
}

export function loadSeenNodes(gameId: string): Set<string> {
  const raw = getStorage()?.getItem(`${SEEN_NODES_PREFIX}${gameId}`);
  if (!raw) return new Set();
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed.filter((s): s is string => typeof s === 'string')) : new Set();
  } catch {
    return new Set();
  }
}

export function storeSeenNodes(gameId: string, ids: Set<string>): void {
  getStorage()?.setItem(`${SEEN_NODES_PREFIX}${gameId}`, JSON.stringify([...ids]));
}

// Clear all per-game UI caches on new-game (avoids stale data leaking to next playthrough).
export function clearAllForGame(gameId: string): void {
  const s = getStorage();
  if (!s) return;
  s.removeItem(`${SUGGESTIONS_PREFIX}${gameId}`);
  s.removeItem(`${LAST_SEEN_LOCATION_PREFIX}${gameId}`);
  s.removeItem(`${LAST_SEEN_QUEST_TITLE_PREFIX}${gameId}`);
  s.removeItem(`${LAST_SEEN_SUBJECT_ID_PREFIX}${gameId}`);
  s.removeItem(`${SEEN_NODES_PREFIX}${gameId}`);
  s.removeItem(`${STORY_GRAPH_PREFIX}${gameId}`);
}
