import { nextShown } from '../reveal';

test('waiting text comes out a little at a time and a rewrite shows at once', () => {
  const full = '봉식아, 큰일 났어! 그게 없어졌다고!';
  let shown = '';
  const steps: string[] = [];
  while (shown !== full) {
    shown = nextShown(shown, full);
    steps.push(shown);
  }
  expect(steps.length).toBeGreaterThan(8);
  expect(steps.every((s) => full.startsWith(s))).toBe(true);
  expect(nextShown('봉식아, 큰일', '다른 글')).toBe('다른 글');
  expect(nextShown(full, full)).toBe(full);
});
