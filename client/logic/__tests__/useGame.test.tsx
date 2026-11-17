/**
 * @jest-environment jsdom
 */
import { randomUUID } from 'node:crypto';
import { act } from 'react';
// @ts-expect-error react-dom is available in Jest but has no local types.
import { createRoot } from 'react-dom/client';

import { useGame } from '../useGame';

jest.mock('@/services/api', () => {
  process.env.EXPO_PUBLIC_API_URL = '/test-api';
  process.env.EXPO_PUBLIC_API_USER = 'local';
  process.env.EXPO_PUBLIC_API_PASS = 'local';
  return jest.requireActual('@/services/api');
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
Object.defineProperty(globalThis.crypto, 'randomUUID', { value: randomUUID });

test('keeps commands locked while checked text appears in order', async () => {
  jest.useFakeTimers({ doNotFake: ['queueMicrotask'] });
  const first = '징수관이 숨졌소. 새벽 종이 울리기 전에 결백을 밝혀야 하오.';
  const second = '창밖에서 종이 울립니다.';
  const responses = [[], { game: 'test', view: { revision: 0 } }, {
    kind: 'turn', turn: 1, said: '무슨 일이 있었습니까?', text: true, view: { revision: 1 },
    feed: [{ kind: 'text', slot: 0, who: '고드릭' }, { kind: 'guide', slot: 1, who: null }],
  }, {
    events: [
      { type: 'start', slot: 0 }, { type: 'delta', slot: 0, text: first }, { type: 'end', slot: 0 },
      { type: 'start', slot: 1 }, { type: 'delta', slot: 1, text: second }, { type: 'end', slot: 1 },
      { type: 'done' },
    ],
    next: 7,
  }];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = jest.fn(async () => ({ ok: true, json: async () => responses.shift() }) as Response);
  const root = createRoot(document.createElement('div'));
  let game!: ReturnType<typeof useGame>;
  function Probe() {
    game = useGame();
    return null;
  }
  const slots = () => game.log.flatMap((entry) => 'slot' in entry ? [[entry.text, entry.complete]] : []);

  try {
    await act(async () => root.render(<Probe />));
    await act(async () => game.start('test'));
    await act(async () => game.send({ text: '무슨 일이 있었습니까?' }));
    expect(game.phase).toBe('streaming');
    expect(slots()).toEqual([[expect.stringMatching(/^징수/), false], ['', false]]);
    expect(slots()[0][0]).not.toBe(first);

    await act(async () => jest.runAllTimersAsync());
    expect(slots()).toEqual([[first, true], [second, true]]);
    expect(game.phase).toBe('ready');
  } finally {
    act(() => root.unmount());
    window.localStorage.clear();
    globalThis.fetch = originalFetch;
    jest.useRealTimers();
  }
});
