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

function radios(tree: ReturnType<typeof renderer.create>) {
  return tree.root.findAll((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function', { deep: false });
}
function dice(tree: ReturnType<typeof renderer.create>) {
  return tree.root.find((n: { props: { accessibilityLabel?: string; onPress?: unknown } }) =>
    n.props.accessibilityLabel === ko.hold && typeof n.props.onPress === 'function');
}

test('the dice roll with the help the player chose, not the one the card opened with', async () => {
  const onRoll = jest.fn();
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card()} onRoll={onRoll} onCancel={jest.fn()} />); });
  await flush(async () => { radios(tree!)[0].props.onPress(); });
  await flush(async () => { dice(tree!).props.onPress(); });
  expect(onRoll).toHaveBeenLastCalledWith('try:door:finesse');
  await flush(async () => { radios(tree!)[0].props.onPress(); });
  await flush(async () => { dice(tree!).props.onPress(); });
  expect(onRoll).toHaveBeenLastCalledWith('try:door:finesse;rely=thing:key');
  await flush(async () => { tree!.unmount(); });
});

test('once rolling, the help, the dice and the close button are locked', async () => {
  const onRoll = jest.fn();
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={card()} onRoll={onRoll} onCancel={jest.fn()} rolling />); });
  expect(radios(tree!)[0].props.disabled).toBe(true);
  expect(dice(tree!).props.disabled).toBe(true);
  expect(labelled(tree!, ko.close)).toBe(false);
  await flush(async () => { tree!.unmount(); });
});

test('a decisive chip says whether it helped or hindered', async () => {
  const step = {
    t: 1, action: 'try:door:finesse', label: 'door', result: 'success' as const, risk: 'normal' as const, dc: 8,
    roll: { d1: 3, d2: 3 }, total: 8, decisive: [1, 2], changes: [],
    mods: [{ kind: 'stat' as const, label: 'finesse', value: 2 }, { kind: 'help' as const, label: 'key', value: 1 },
      { kind: 'hinder' as const, label: 'storm', value: -1 }],
  };
  const frame = {
    step: 0, dice: [3, 3] as [number, number], point: 8, chips: 3, settled: 'success', decisive: [1, 2], boxes: {},
    folded: false, changes: [], blocked: null, done: true,
  };
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => {
    tree = renderer.create(<RollCard card={card()} step={step} frame={frame} onRoll={jest.fn()} onCancel={jest.fn()} />);
  });
  expect(texts(tree!)).toContain(`key +1 ${ko.thanks}`);
  expect(texts(tree!)).toContain(`storm −1 ${ko.because}`);
  await flush(async () => { tree!.unmount(); });
});

test('forcing toggles to the same reliance in the other strain and says what it buys', async () => {
  const onRoll = jest.fn();
  const forcedPreview = { ...preview(3, 'high', 1), gain: { kind: 'fill' as const, boxes: 3, fit: 1, forced: 1 } };
  const c = { ...card(), options: [
    { id: 'try:door:finesse;rely=thing:key', label: 'key', rely: 'thing:key', forced: false, preview: preview(3, 'normal', 1) },
    { id: 'try:door:finesse', label: 'none', rely: null, forced: false, preview: preview(2) },
    { id: 'try:door:finesse;rely=thing:key;strain=forced', label: 'key', rely: 'thing:key', forced: true, preview: forcedPreview },
    { id: 'try:door:finesse;strain=forced', label: 'none', rely: null, forced: true, preview: { ...forcedPreview, z: 2 } },
  ] } as Card;
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={c} onRoll={onRoll} onCancel={jest.fn()} />); });
  const box = () => tree!.root.find((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'checkbox' && typeof n.props.onPress === 'function');
  expect(box().props.accessibilityLabel).toBe(`${ko.forced} · ${ko.forcedGain}`);
  expect(box().props.accessibilityState.checked).toBe(false);
  await flush(async () => { box().props.onPress(); });
  expect(box().props.accessibilityState.checked).toBe(true);
  expect(labelled(tree!, ko.highRisk)).toBe(true);
  const radios = tree!.root.findAll((n: { props: { accessibilityRole?: string; onPress?: unknown } }) =>
    n.props.accessibilityRole === 'radio' && typeof n.props.onPress === 'function', { deep: false });
  expect(radios).toHaveLength(1);
  expect(radios[0].props.accessibilityState.checked).toBe(true);
  await flush(async () => { tree!.unmount(); });
});

test('a spent reliance reads as a lower stake, not a number', async () => {
  const guard = { ...preview(2), mods: [{ kind: 'stat' as const, label: 'finesse', value: 2 }, { kind: 'guard' as const, label: 'key', value: 0 }] };
  const c = { ...card(), options: [{ ...card().options[0], preview: guard }, card().options[1]] } as Card;
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => { tree = renderer.create(<RollCard card={c} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(labelled(tree!, `key · ${ko.guarded}`)).toBe(true);
  expect(texts(tree!)).not.toContain('±0');
  await flush(async () => { tree!.unmount(); });
});

test('the ring is explained once a game: the target on the first card, the red ring the first time it is red', async () => {
  let tree: ReturnType<typeof renderer.create>;
  await flush(async () => {
    tree = renderer.create(<RollCard card={card()} explain={{ target: true, high: true }} onRoll={jest.fn()} onCancel={jest.fn()} />);
  });
  expect(texts(tree!)).toContain('8 이상');
  expect(texts(tree!)).not.toContain(ko.irreversible);                 // not red
  await flush(async () => {
    tree!.update(<RollCard card={card('high')} explain={{ target: false, high: true }} onRoll={jest.fn()} onCancel={jest.fn()} />);
  });
  expect(texts(tree!)).toContain(ko.irreversible);
  expect(texts(tree!)).not.toContain('이상');
  await flush(async () => { tree!.update(<RollCard card={card('high')} onRoll={jest.fn()} onCancel={jest.fn()} />); });
  expect(texts(tree!)).not.toContain(ko.irreversible);
});
