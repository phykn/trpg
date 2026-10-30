// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { ClarifyCard } from '@/components/game/ClarifyCard';
import { ConfirmCard } from '@/components/game/ConfirmCard';
import { ko } from '@/locale/ko';
import type { Card } from '@/services/types';

type Node = { props: Record<string, unknown> };
const pressable = (tree: { root: { findAll: (f: (n: Node) => boolean) => Node[] } }, label: string) =>
  tree.root.findAll((n) => n.props.accessibilityLabel === label && typeof n.props.onPress === 'function');

const clarify = {
  id: 'c7', kind: 'clarify', echo: { text: '그에게 말한다', slots: [] }, question: '누구에게 말할까요?',
  plan: { step: null, rest: [] },
  options: [{ id: 'talk:yunseul', label: '윤슬에게 말을 건다' }, { id: 'talk:dohae', label: '도해에게 말을 건다' }],
  selected: null,
} as unknown as Card;

const confirm = {
  id: 'c8', kind: 'confirm', echo: { text: '배를 태운다', slots: [] }, plan: { step: null, rest: [] },
  options: [{ id: 'fork:burn', label: '배를 태운다', effects: ['돌아갈 길이 사라짐', '도해의 신뢰를 잃음'] }],
  selected: 'fork:burn',
} as unknown as Card;

test('a clarify card asks its question and answers with the chosen option id', async () => {
  const onPick = jest.fn();
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<ClarifyCard card={clarify} onPick={onPick} onCancel={jest.fn()} />); });
  const text = JSON.stringify(tree!.toJSON());
  expect(text).toContain('누구에게 말할까요?');
  expect(text).not.toContain('talk:');
  await flush(async () => { (pressable(tree!, '도해에게 말을 건다')[0].props.onPress as () => void)(); });
  expect(onPick).toHaveBeenCalledWith('talk:dohae');
});

test('a way round that rolls shows its target number, and whether failing costs for good', async () => {
  const detour = { ...clarify, options: [
    { id: 'try:hound:charm', label: '달랜다', dc: 7, risk: 'low' },
    { id: 'try:hound:force', label: '밀친다', dc: 9, risk: 'high' },
  ] } as unknown as Card;
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<ClarifyCard card={detour} onPick={jest.fn()} onCancel={jest.fn()} />); });
  expect(pressable(tree!, '달랜다, 7 이상')).toHaveLength(1);
  expect(pressable(tree!, `밀친다, 9 이상 · ${ko.irreversible}`)).toHaveLength(1);
});

test('a confirm card lists what the choice costs and commits with its option id', async () => {
  const onPick = jest.fn();
  const onCancel = jest.fn();
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<ConfirmCard card={confirm} onPick={onPick} onCancel={onCancel} />); });
  const text = JSON.stringify(tree!.toJSON());
  expect(text).toContain('돌아갈 길이 사라짐');
  expect(text).toContain('도해의 신뢰를 잃음');
  await flush(async () => { (pressable(tree!, ko.choose)[0].props.onPress as () => void)(); });
  expect(onPick).toHaveBeenCalledWith('fork:burn');
  await flush(async () => { (pressable(tree!, ko.close)[0].props.onPress as () => void)(); });
  expect(onCancel).toHaveBeenCalled();
});

test('a give confirm card also offers to show the thing only', async () => {
  const onPick = jest.fn();
  const give = { ...confirm, options: [
    { id: 'give:letter:yunseul', label: '윤슬에게 아들의 편지를 준다', effects: ['아들의 편지가 윤슬에게 감'] },
    { id: 'show:letter:yunseul', label: '윤슬에게 아들의 편지를 보여 준다', effects: [] },
  ] } as Card;
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<ConfirmCard card={give} onPick={onPick} onCancel={jest.fn()} />); });
  await flush(async () => { (pressable(tree!, '윤슬에게 아들의 편지를 보여 준다')[0].props.onPress as () => void)(); });
  expect(onPick).toHaveBeenCalledWith('show:letter:yunseul');
});
