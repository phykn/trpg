import { loadSuggestions, storeSuggestions } from '../storage';

const storage = new Map<string, string>();

beforeEach(() => {
  storage.clear();
  const mockStorage: Storage = {
    get length() {
      return storage.size;
    },
    clear: () => storage.clear(),
    getItem: (key: string) => storage.get(key) ?? null,
    key: (index: number) => [...storage.keys()][index] ?? null,
    removeItem: (key: string) => {
      storage.delete(key);
    },
    setItem: (key: string, value: string) => {
      storage.set(key, value);
    },
  };
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { localStorage: mockStorage },
  });
});

afterEach(() => {
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: undefined,
  });
});

describe('suggestion storage', () => {
  test('loads legacy string suggestions as chips', () => {
    storage.set('trpg.suggestions.game-1', JSON.stringify(['북문으로 이동합니다']));

    expect(loadSuggestions('game-1')).toEqual([
      { label: '북문으로 이동합니다', inputText: '북문으로 이동합니다' },
    ]);
  });

  test('stores chip suggestions without degrading input text', () => {
    storeSuggestions('game-1', [
      { label: '북문으로', inputText: '북문으로 이동합니다', intent: 'move' },
    ]);

    expect(JSON.parse(storage.get('trpg.suggestions.game-1') ?? 'null')).toEqual([
      { label: '북문으로', inputText: '북문으로 이동합니다', intent: 'move' },
    ]);
  });
});
