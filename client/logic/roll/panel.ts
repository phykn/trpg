export type DiceCellBand = 'fail' | 'success';

export type DiceCell = {
  value: number;
  band: DiceCellBand;
  selected: boolean;
};

export function buildDiceCells(requiredRoll: number): DiceCell[] {
  const threshold = Math.max(1, Math.min(20, Math.trunc(requiredRoll)));
  return Array.from({ length: 20 }, (_, index) => {
    const value = index + 1;
    return {
      value,
      band: value >= threshold ? 'success' : 'fail',
      selected: value === threshold,
    };
  });
}

