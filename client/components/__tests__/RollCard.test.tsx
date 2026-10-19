// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';
import { Text } from 'react-native';

import { RollCard } from '@/components/game/RollCard';
import { ko } from '@/locale/ko';
import type { Card, Preview } from '@/services/types';

// eslint-disable-next-line @typescript-eslint/no-require-imports
jest.mock('react-native-reanimated', () => ({ ...require('react-native-reanimated/mock'), useReducedMotion: () => true }));

const preview = (z: number, risk: Preview['risk'] = 'normal', help = 0): Preview => ({
  risk, z, dc: risk === 'high' ? 9 : 8,
  mods: [{ kind: 'stat', label: 'finesse', value: 2 }, ...(help ? [{ kind: 'help' as const, label: 'key', value: help }] : [])],
  stakes: { clock: 1, weight: 'light' },
  clock: { id: 'clock.1', name: 'storm', boxes: 4, fill: 1 }, gain: { kind: 'fill', boxes: 2, fit: 1 },
});
const card = (risk: Preview['risk'] = 'normal'): Card => ({
  id: 'c1', kind: 'roll', echo: { text: 'turn the key', slots: [{ slot: 'approach', label: 'finesse' }] },
  plan: { step: { action: 'try:door:finesse', label: 'door', target: { id: 'door', name: 'Door', fill: 0, boxes: 3 } }, rest: [] },
  options: [
    { id: 'try:door:finesse;rely=thing:key', label: 'key', consumed: false, note: null, preview: preview(3, risk, 1) },
    { id: 'try:door:finesse', label: 'none', consumed: false, note: null, preview: preview(2, risk) },
  ],
  selected: 'try:door:finesse;rely=thing:key',
});

function labelled(tree: { root: { findAll: (f: (n: { props: { accessibilityLabel?: string } }) => boolean) => unknown[] } }, label: string) {
  return tree.root.findAll((n) => n.props.accessibilityLabel === label).length > 0;
}

function texts(tree: { root: { findAllByType: (t: unknown) => { props: { children: unknown } }[] } }): string {
  return tree.root.findAllByType(Text).map((t) => [t.props.children].flat(3).join('')).join('|');
}

test('the card shows the attempt and target number and toggles reliance chips', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card()} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(texts(tree!)).toContain('door');
  expect(texts(tree!)).toContain('8');
  expect(texts(tree!)).not.toContain('none');
  const chips = tree!.root.findAll((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function', { deep: false });
  expect(chips).toHaveLength(1);
  expect(chips[0].props.accessibilityState.checked).toBe(true);
  await flush(async () => { chips[0].props.onPress(); });
  const again = tree!.root.findAll((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function', { deep: false });
  expect(again[0].props.accessibilityState.checked).toBe(false);
  expect(labelled(tree!, ko.highRisk)).toBe(false);
  await flush(async () => { tree!.unmount(); });
});

test('a high risk card warns', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card('high')} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(labelled(tree!, ko.highRisk)).toBe(true);
  expect(texts(tree!)).toContain('9');
  await flush(async () => { tree!.unmount(); });
});
