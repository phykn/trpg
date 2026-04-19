import type { Check, RollResult } from '@/types/domain';

export function checkPrompt(check: Check): string {
  return `${check.stat} 판정이 필요합니다 (난이도 ${check.dc})`;
}

const ROLL_FOLLOWUPS: Record<RollResult, string> = {
  success: '두목의 시선을 훌륭히 피했다. 기회가 왔다.',
  fail: '발밑의 자갈이 굴렀다. 두목이 당신을 노려본다.',
};

export function rollFollowup(result: RollResult): string {
  return ROLL_FOLLOWUPS[result];
}
