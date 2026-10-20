// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { Scene } from '@/components/game/Scene';
import type { GameView } from '@/services/types';

const scene = (fill: number) => ({
  place: { id: 'yard', name: '등대 앞', senses: [] },
  people: [], things: [], tags: [],
  obstacles: [{ id: 'door', name: '녹슨 등대 문', fill, boxes: 1, blocks: ['등불실'] }],
  exits: [{ id: 'dock', name: '선착장', blocked: false }, { id: 'lamp_room', name: '등불실', blocked: fill < 1 }],
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
  await flush(async () => { pill(tree, '등불실')[0].props.onPress?.(); });
  expect(onDraft.mock.calls.map((c) => c[0])).toEqual(['선착장으로 간다', '녹슨 등대 문을 ']);
});

test('an overcome obstacle takes no draft', async () => {
  const tree = await render(1, jest.fn());
  expect(pill(tree, '녹슨 등대 문')).toHaveLength(0);
});

test('a companion carries the person icon', async () => {
  const withPeople = { ...scene(1), people: [
    { id: 'yunseul', name: '윤슬', attitude: '', with: true }, { id: 'dohae', name: '도해', attitude: '', with: false },
  ] } as unknown as GameView['scene'];
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<Scene scene={withPeople} onDraft={jest.fn()} />); });
  const icon = (name: string) => tree!.root.findAll((n: { props: Record<string, unknown> }) => n.props.label === name && 'icon' in n.props)[0].props.icon;
  expect([icon('윤슬'), icon('도해')]).toEqual(['user', undefined]);
});
