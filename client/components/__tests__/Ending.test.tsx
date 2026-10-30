// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { Ending } from '@/components/game/Ending';
import type { GameView } from '@/services/types';

const view = {
  ending: { id: 'shared', title: '나눈 약' }, recaps: [1],
  journal: { beliefs: [], owes: [], relations: [], choices: [{ kind: 'fork', name: '약 절반을 남긴다', chapter: 2 }] },
  ledger: [
    { chapter: 1, lines: [{ kind: 'give', text: '방울이 잎담배 쌈지를 얻었습니다' }] },
    { chapter: 2, lines: [{ kind: 'promise', state: 'kept', text: '당신은 방울과의 약속을 지켰습니다' }] },
  ],
} as unknown as GameView;

test('each chapter shows its recap, then what was chosen and what passed with people', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Ending view={view} recaps={{ 1: '눈을 퍼냈습니다.' }} onNew={jest.fn()} />); });
  const text = JSON.stringify(tree!.toJSON());
  const order = ['1장', '눈을 퍼냈습니다.', '방울이 잎담배 쌈지를 얻었습니다', '2장', '약 절반을 남긴다', '당신은 방울과의 약속을 지켰습니다'];
  expect(order.map((t) => text.indexOf(t))).toEqual([...order.map((t) => text.indexOf(t))].sort((a, b) => a - b));
  expect(order.every((t) => text.includes(t))).toBe(true);
});
