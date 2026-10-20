// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { Clocks } from '@/components/game/Clocks';
import type { GameView } from '@/services/types';

const clocks = [
  { id: 'clock.1', name: '몰려오는 폭풍', fill: 1, boxes: 4, kind: 'clock' },
  { id: 'deadline.1', name: '해가 진다', fill: 1, boxes: 3, kind: 'deadline' },
] as GameView['clocks'];

test('a deadline shows the scene time spent in its next box; a risk clock does not', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Clocks clocks={clocks} time={0.5} />); });
  const parts = tree!.root.findAll((n: { type: unknown; props: { style?: { height?: string } } }) =>
    n.props.style?.height === '50%' && n.type === 'View');
  expect(parts).toHaveLength(1);
});
