// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { Scene } from '@/components/game/Scene';
import type { GameView } from '@/services/types';

const scene = (fill: number) => ({
  place: { id: 'yard', name: '등대 앞', senses: [] },
  people: [], things: [], tags: [],
  obstacles: [{ id: 'door', name: '녹슨 등대 문', fill, boxes: 1, blocks: ['등불 방'] }],
  exits: [{ id: 'dock', name: '선착장', blocked: false }, { id: 'lamp_room', name: '등불 방', blocked: fill < 1 }],
}) as unknown as GameView['scene'];

// The pills a tap can start a sentence from, by name.
function pill(tree: { root: { findAll: (f: (n: { props: Record<string, unknown> }) => boolean) => { props: { onPress?: () => void } }[] } }, name: string) {
  return tree.root.findAll((n) => n.props.label === name && typeof n.props.onPress === 'function');
}

async function render(fill: number, onDraft: (t: string) => void) {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Scene scene={scene(fill)} onDraft={onDraft} />); });
  return tree!;
}

test('an open way drafts going there, a locked way drafts its lock', async () => {
  const onDraft = jest.fn();
  const tree = await render(0, onDraft);
  await flush(async () => { pill(tree, '선착장')[0].props.onPress?.(); });
  await flush(async () => { pill(tree, '등불 방')[0].props.onPress?.(); });
  expect(onDraft.mock.calls.map((c) => c[0])).toEqual(['선착장으로 간다', '녹슨 등대 문을 ']);
});

test('an overcome obstacle takes no draft', async () => {
  const tree = await render(1, jest.fn());
  expect(pill(tree, '녹슨 등대 문')).toHaveLength(0);
});
