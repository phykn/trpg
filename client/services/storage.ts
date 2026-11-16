const KEY = 'trpg.game_id';

// A private window or a full disk refuses storage; the game goes on, it just cannot be reopened later.
function withStorage<T>(work: (storage: Storage) => T): T | null {
  try {
    return work(window.localStorage);
  } catch {
    return null;
  }
}

export const loadGameId = () => withStorage((s) => s.getItem(KEY));
export const storeGameId = (id: string) => void withStorage((s) => s.setItem(KEY, id));
export const clearGameId = () => void withStorage((s) => s.removeItem(KEY));
