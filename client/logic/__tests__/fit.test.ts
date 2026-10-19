import { text } from '@/design/tokens';
import { fitSize, linesAt } from '../fit';

const NARRATION = '젖은 길을 따라 마을로 내려갑니다. 낮은 지붕들 위로 회색 구름이 깔려 있고 바람이 덧문을 흔듭니다. '.repeat(4).slice(0, 200);

test('200 characters fit the smallest narration area at 320×568 in 13px', () => {
  expect(NARRATION.length).toBe(200);
  expect(fitSize(NARRATION, 288, 232, text.narration, text.lineHeight)).toBeGreaterThanOrEqual(text.min);
  expect(linesAt(NARRATION, 13, 288) * 13 * text.lineHeight).toBeLessThanOrEqual(232);
});

test('a smaller area takes a smaller size, never below the floor', () => {
  const roomy = fitSize(NARRATION, 380, 600, text.narration, text.lineHeight);
  const tight = fitSize(NARRATION, 288, 180, text.narration, text.lineHeight);
  expect(roomy).toBe(text.narration[0]);
  expect(tight).toBeLessThan(roomy);
  expect(fitSize(NARRATION, 100, 40, text.narration, text.lineHeight)).toBe(text.min);
});
