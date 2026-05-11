import { mergeAndStoreStoryGraph } from '../useStoryGraph';
import type { StoryGraphModel } from '../types';

const risk = { label: '보통', tone: 'neutral' as const };

function graph(): StoryGraphModel {
  return {
    summary: '광장',
    nodes: [
      {
        id: 'town',
        label: '광장',
        kind: 'place',
        status: 'current',
        reachable: true,
        description: '사람들이 모여 있습니다.',
        risk,
        dayPhase: '',
        weather: [],
      },
    ],
    edges: [],
  };
}

function storage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear: jest.fn(() => data.clear()),
    getItem: jest.fn((key: string) => data.get(key) ?? null),
    key: jest.fn((index: number) => Array.from(data.keys())[index] ?? null),
    removeItem: jest.fn((key: string) => {
      data.delete(key);
    }),
    setItem: jest.fn((key: string, value: string) => {
      data.set(key, value);
    }),
  };
}

describe('mergeAndStoreStoryGraph', () => {
  const originalWindow = globalThis.window;
  const originalCustomEvent = globalThis.CustomEvent;

  afterEach(() => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow,
    });
    Object.defineProperty(globalThis, 'CustomEvent', {
      configurable: true,
      value: originalCustomEvent,
    });
  });

  test('does not require CustomEvent in native-like runtimes', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        localStorage: storage(),
        dispatchEvent: jest.fn(),
      },
    });
    Object.defineProperty(globalThis, 'CustomEvent', {
      configurable: true,
      value: undefined,
    });

    expect(() => mergeAndStoreStoryGraph('game-1', graph())).not.toThrow();
  });
});
