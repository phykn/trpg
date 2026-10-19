// @ts-expect-error react-test-renderer is available in Jest but has no local types.
import renderer, { act as flush } from 'react-test-renderer';
import { Text } from 'react-native';

import { RollCard } from '@/components/game/RollCard';
import { ko } from '@/locale/ko';
import type { Card, Preview } from '@/services/types';

// eslint-disable-next-line @typescript-eslint/no-require-imports
jest.mock('react-native-reanimated', () => ({ ...require('react-native-reanimated/mock'), useReducedMotion: () => true }));

const preview = (z: number, risk: Preview['risk'] = 'normal', help = 0): Preview => ({
  risk, z, odds: { fail: 0.2 - z / 100, mixed: 0.4, success: 0.4 + z / 100 },
  mods: [{ kind: 'stat', label: 'finesse', value: 2 }, ...(help ? [{ kind: 'help' as const, label: 'key', value: help }] : [])],
  stakes: { mixed: { clock: 1, weight: 'light' }, fail: { clock: 1, weight: 'heavy' } },
  clock: { id: 'clock.1', name: 'storm', boxes: 4, fill: 1 }, gain: { kind: 'fill', boxes: 2, fit: 1 },
});
const card = (risk: Preview['risk'] = 'normal'): Card => ({
  id: 'c1', kind: 'roll', echo: { text: 'turn the key', slots: [{ slot: 'approach', label: 'finesse' }] },
  plan: { step: { action: 'try:door:finesse', label: 'door', target: { id: 'door', name: 'Door', fill: 0, boxes: 3 } }, rest: [] },
  options: [
    { id: 'try:door:finesse;rely=thing:key', label: 'key', consumed: false, note: null, preview: preview(3, risk, 1) },
    { id: 'try:door:finesse', label: ko.result.none || 'none', consumed: false, note: null, preview: preview(2, risk) },
  ],
  selected: 'try:door:finesse;rely=thing:key',
});

function texts(tree: { root: { findAllByType: (t: unknown) => { props: { children: unknown } }[] } }): string {
  return tree.root.findAllByType(Text).map((t) => [t.props.children].flat(3).join('')).join('|');
}

test('the selected reliance is drawn first, and picking another draws its preview', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card()} bands={{ mixed: 7, success: 10, min: 1, max: 16 }} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(texts(tree!)).toContain(ko.odds(ko.result.success, 0.43));
  const radios = tree!.root.findAll((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function', { deep: false });
  expect(radios[0].props.accessibilityState.selected).toBe(true);
  await flush(async () => { radios[1].props.onPress(); });
  expect(texts(tree!)).toContain(ko.odds(ko.result.success, 0.42));
  expect(texts(tree!)).not.toContain(ko.highRisk);
  await flush(async () => { tree!.unmount(); });
});

test('a high risk card warns', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card('high')} bands={{ mixed: 7, success: 10, min: 1, max: 16 }} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(texts(tree!)).toContain(ko.highRisk);
  await flush(async () => { tree!.unmount(); });
});
