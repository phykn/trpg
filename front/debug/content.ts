import type { Check } from '@/services';
import type { RollResult } from '@/types/domain';

const GM_TEMPLATES = [
  '횃불이 흔들리며, 당신의 그림자가 벽에 길게 늘어진다.',
  '두목이 으르렁거린다. "그 말을 믿으라고?"',
  '멀리서 쇠사슬이 끌리는 소리. 뭔가 다가오고 있다.',
  '돌바닥에 흩어진 피 자국. 아직 마르지 않았다.',
  '당신의 심장이 요동친다. 판단할 시간은 얼마 없다.',
  '두목이 한 걸음 물러서며 이빨을 드러냈다. "재미있군."',
  '공기가 차갑다. 동굴 깊은 곳에서 낮은 진동이 느껴진다.',
  '당신의 인장 반지가 희미하게 빛난다 — 마법의 흔적.',
];

export function fakeGMReply(_playerText: string): string {
  const pool = [...GM_TEMPLATES].sort(() => Math.random() - 0.5);
  const n = Math.random() < 0.4 ? 2 : 1;
  return pool.slice(0, n).join(' ');
}

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
