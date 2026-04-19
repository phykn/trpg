import type { StatKey, RollResult } from '@/types/domain';

export type Check = {
  stat: StatKey;
  dc: number;
  mod: number;
};

export function rollD20(): number {
  return 1 + Math.floor(Math.random() * 20);
}

export function resolveCheck(check: Check, roll: number): RollResult {
  return roll + check.mod >= check.dc ? 'success' : 'fail';
}
