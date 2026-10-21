import type { Change, StepRecord } from '@/services/types';

type Motion = {
  die: number; dieGap: number; line: number; chip: number; settle: number; decisive: number;
  box: number; fold: number; change: number; blockedFade: number; reduced: number;
};

type Base = { step: number; at: number; dur: number };
export type Beat = Base & (
  | { kind: 'die'; which: 1 | 2; value: number }
  | { kind: 'line'; value: number }
  | { kind: 'chip'; index: number; value: number }
  | { kind: 'settle'; value: number; result: string }
  | { kind: 'decisive'; index: number }
  | { kind: 'box'; change: number }
  | { kind: 'fold' }
  | { kind: 'change'; change: number }
  | { kind: 'blocked'; names: string[] }
);

const ROW_KINDS = new Set(['fill', 'clock', 'crisis', 'arrival']);

function boxBeats(c: Change): number {
  if (c.kind === 'fill' || c.kind === 'clock') return Math.max(1, Math.abs((c.to as number) - (c.from as number)));
  return 1;
}

export function rolled(step: StepRecord): step is StepRecord & { roll: NonNullable<StepRecord['roll']> } {
  return step.roll !== null && step.result !== 'blocked';
}

export function timeline(steps: StepRecord[], motion: Motion, reduced = false): Beat[] {
  const beats: Beat[] = [];
  let t = 0;
  const push = (step: number, dur: number, beat: Record<string, unknown>, overlap = 0) => {
    const d = reduced ? motion.reduced : dur;
    const at = reduced ? t : t - overlap;
    beats.push({ step, at, dur: d, ...beat } as Beat);
    t = Math.max(t, at + d);
  };
  steps.forEach((s, i) => {
    if (s.result === 'blocked') {
      const names = s.changes.filter((c) => c.kind === 'reveal').map((c) => c.name as string);
      push(i, motion.blockedFade, { kind: 'blocked', names });
      if (s.roll) push(i, motion.fold, { kind: 'fold' });
      s.changes.forEach((_, c) => push(i, motion.change, { kind: 'change', change: c }));
      return;
    }
    if (rolled(s)) {
      const roll = s.roll;
      push(i, motion.die, { kind: 'die', which: 1, value: roll.d1 });
      // d2 starts dieGap after d1 starts: the only overlap.
      push(i, motion.die, { kind: 'die', which: 2, value: roll.d2 }, motion.die - motion.dieGap);
      let value = roll.d1 + roll.d2;
      push(i, motion.line, { kind: 'line', value });
      s.mods.forEach((m, index) => {
        value += m.value;
        push(i, motion.chip, { kind: 'chip', index, value });
      });
      push(i, motion.settle, { kind: 'settle', value: s.total ?? value, result: s.result });
      s.decisive.forEach((index) => push(i, motion.decisive, { kind: 'decisive', index }));
    }
    s.changes.forEach((c, change) => {
      if (!ROW_KINDS.has(c.kind)) return;
      for (let b = 0; b < boxBeats(c); b += 1) push(i, motion.box, { kind: 'box', change });
    });
    if (rolled(s)) push(i, motion.fold, { kind: 'fold' });
    s.changes.forEach((c, change) => {
      if (!ROW_KINDS.has(c.kind)) push(i, motion.change, { kind: 'change', change });
    });
  });
  return beats;
}

export function duration(beats: Beat[]): number {
  return beats.reduce((end, b) => Math.max(end, b.at + b.dur), 0);
}

export type Frame = {
  step: number;
  dice: [number | null, number | null];
  point: number | null;
  chips: number;
  settled: string | null;
  decisive: number[];
  boxes: Record<number, number>;   // change index → boxes shown so far
  folded: boolean;
  changes: number[];
  blocked: string[] | null;
  done: boolean;
};

export function frame(beats: Beat[], elapsed: number): Frame {
  const started = beats.filter((b) => b.at <= elapsed);
  const current = started.length ? started[started.length - 1].step : 0;
  const mine = started.filter((b) => b.step === current);
  const f: Frame = {
    step: current, dice: [null, null], point: null, chips: 0, settled: null, decisive: [], boxes: {},
    folded: false, changes: [], blocked: null, done: elapsed >= duration(beats),
  };
  for (const b of mine) {
    if (b.kind === 'die') f.dice[b.which - 1] = b.value;
    else if (b.kind === 'line') f.point = b.value;
    else if (b.kind === 'chip') { f.point = b.value; f.chips = b.index + 1; }
    else if (b.kind === 'settle') { f.point = b.value; f.settled = b.result; }
    else if (b.kind === 'decisive') f.decisive.push(b.index);
    else if (b.kind === 'box') f.boxes[b.change] = (f.boxes[b.change] ?? 0) + 1;
    else if (b.kind === 'fold') f.folded = true;
    else if (b.kind === 'change') f.changes.push(b.change);
    else if (b.kind === 'blocked') f.blocked = b.names;
  }
  return f;
}
