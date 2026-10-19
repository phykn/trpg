// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act } from 'react-test-renderer';

import { loadLog, storeLog } from '@/services/storage';
import { useLog } from '../useLog';

jest.mock('@/services/storage', () => ({ loadLog: jest.fn(() => []), storeLog: jest.fn() }));

function mount(gameId: string, premise: string) {
  const out: { current: ReturnType<typeof useLog> | null } = { current: null };
  function Probe() { out.current = useLog(gameId, premise); return null; }
  act(() => { renderer.create(<Probe />); });
  return out;
}

test('a new game starts with the premise and a replayed turn is not logged twice', () => {
  const log = mount('g1', '등대가 꺼졌습니다.');
  expect(log.current!.entries).toEqual([{ id: 'premise', kind: 'story', text: '등대가 꺼졌습니다.' }]);
  act(() => log.current!.add({ id: 'story:1', kind: 'story', text: 'a' }));
  act(() => log.current!.add({ id: 'story:1', kind: 'story', text: 'a' }));
  expect(log.current!.entries.map((e) => e.id)).toEqual(['premise', 'story:1']);
  expect(log.current!.has('story:1')).toBe(true);
  expect(storeLog).toHaveBeenCalledTimes(1);
});

test('a saved log is restored instead of the premise', () => {
  (loadLog as jest.Mock).mockReturnValueOnce([{ id: 'you:1', kind: 'you', text: '문을 연다' }]);
  const log = mount('g2', '등대가 꺼졌습니다.');
  expect(log.current!.entries.map((e) => e.id)).toEqual(['you:1']);
});
