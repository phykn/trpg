// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';

import { MoveCard } from '@/components/game/MoveCard';
import type { Card } from '@/services/types';

const card = {
  id: 'c3', kind: 'move', echo: { text: '등대 쪽으로', slots: [] }, plan: { step: null, rest: [] },
  options: [
    { id: 'go:yard', label: '등대 앞', effects: ['윤슬과 함께'] },
    { id: 'go:dock', label: '선착장', effects: ['윤슬과 함께'] },
  ],
  selected: 'go:yard',
} as unknown as Card;

test('the chosen way leads in gold, says who comes, and one tap leaves', async () => {
  const onPick = jest.fn();
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<MoveCard card={card} onPick={onPick} onCancel={jest.fn()} />); });
  const rows = tree!.root.findAll((n: { props: Record<string, unknown> }) =>
    typeof n.props.label === 'string' && typeof n.props.onPress === 'function' && 'primary' in n.props);
  expect(rows.map((r: { props: { label: string; primary?: boolean; sub?: string } }) =>
    [r.props.label, !!r.props.primary, r.props.sub])).toEqual([['등대 앞', true, '윤슬과 함께'], ['선착장', false, '윤슬과 함께']]);
  await flush(async () => { rows[1].props.onPress(); });
  expect(onPick).toHaveBeenCalledWith('go:dock');
});

test('a way the sentence named alone asks only whether to go there', async () => {
  const onPick = jest.fn();
  const one = { ...card, options: [card.options[0]] } as Card;
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<MoveCard card={one} onPick={onPick} onCancel={jest.fn()} />); });
  const text = JSON.stringify(tree!.toJSON());
  expect(text).toContain('등대 앞으로 갈까요?');
  expect(text).toContain('윤슬과 함께');
  const go = tree!.root.find((n: { props: Record<string, unknown> }) => n.props.label === '간다' && typeof n.props.onPress === 'function');
  await flush(async () => { go.props.onPress(); });
  expect(onPick).toHaveBeenCalledWith('go:yard');
});
