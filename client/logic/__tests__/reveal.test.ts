import { motion } from '@/design/tokens';
import type { StepRecord } from '@/services/types';
import { duration, frame, timeline } from '../reveal';

const rolledStep: StepRecord = {
  t: 2, action: 'try:door:finesse', label: '녹슨 등대 문에 솜씨로 맞선다', result: 'success', risk: 'normal', dc: 8,
  roll: { d1: 3, d2: 6 }, total: 10, decisive: [0],
  mods: [{ kind: 'stat', label: 'finesse', value: 2 }, { kind: 'hinder', label: 'spray', value: -1 }],
  changes: [{ kind: 'fill', id: 'door', name: 'door', from: 0, to: 2, fit: 1 }, { kind: 'tag_add', owner: 'player', slot: 1 }],
};
const walk: StepRecord = {
  t: 0, action: 'go:village', label: 'go', result: 'none', risk: 'low', dc: null, roll: null, total: null, decisive: [], mods: [],
  changes: [{ kind: 'clock', id: 'clock.1', name: 'storm', from: 0, to: 1 }],
};

test('a rolled step runs dice, line, chips in mods order, settle, decisive, boxes, fold, then changes', () => {
  const beats = timeline([rolledStep], motion);
  expect(beats.map((b) => b.kind)).toEqual(['die', 'die', 'line', 'chip', 'chip', 'settle', 'decisive', 'box', 'box', 'fold', 'change']);
  const [d1, d2] = beats;
  expect(d2.at - d1.at).toBe(motion.dieGap);
  const chips = beats.filter((b) => b.kind === 'chip');
  expect(chips.map((b) => (b as { value: number }).value)).toEqual([11, 10]);
  expect(beats.find((b) => b.kind === 'decisive')).toMatchObject({ index: 0, word: 'thanks' });
});

test('frames carry the running point and what has happened so far', () => {
  const beats = timeline([rolledStep], motion);
  const lineAt = beats.find((b) => b.kind === 'line')!.at;
  expect(frame(beats, lineAt)).toMatchObject({ dice: [3, 6], point: 9, chips: 0, settled: null });
  const end = frame(beats, duration(beats));
  expect(end).toMatchObject({ point: 10, chips: 2, settled: 'success', decisive: [0], folded: true, done: true });
  expect(end.boxes[0]).toBe(2);
});

test('a step without a roll only fills rows and applies changes', () => {
  expect(timeline([walk], motion).map((b) => b.kind)).toEqual(['box']);
  expect(timeline([walk, rolledStep], motion)[1]).toMatchObject({ kind: 'die', step: 1 });
});

test('a blocked step fades the dice and names what showed up', () => {
  const blocked: StepRecord = { ...rolledStep, result: 'blocked', changes: [{ kind: 'reveal', id: 'hound', name: 'hound' }] };
  const beats = timeline([blocked], motion);
  expect(beats.map((b) => b.kind)).toEqual(['blocked', 'fold', 'change']);
  expect(frame(beats, 0).blocked).toEqual(['hound']);
});

test('reduced motion shows each beat for the same short time, one after another', () => {
  const beats = timeline([rolledStep], motion, true);
  expect(beats.every((b) => b.dur === motion.reduced)).toBe(true);
  expect(beats[1].at).toBe(beats[0].at + motion.reduced);
});
