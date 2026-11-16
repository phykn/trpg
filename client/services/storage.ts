const KEY = 'trpg.game_id';

// A private window or a full disk refuses storage; the game goes on, it just cannot be reopened later.
export function loadGameId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function storeGameId(id: string) {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    // see above
  }
}

export function clearGameId() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // see above
  }
}
