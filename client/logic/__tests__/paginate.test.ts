import { pageAt, paginate } from '../paginate';

test('preserves every character, punctuation and paragraph break across pages', () => {
  const text = '그는 문 앞에 서 있습니다.\n\n“당신을 기다렸습니다.”  다음 길로 갑니다. 🌙';
  const pages = paginate(text, (part) => Array.from(part).length <= 18);
  expect(pages.map((page) => page.text).join('')).toBe(text);
  expect(pages.every((page) => Array.from(page.text).length <= 18)).toBe(true);
  expect(pages.map((page) => text.slice(page.start, page.end))).toEqual(pages.map((page) => page.text));
});

test('uses measured fitting rather than a fixed character budget', () => {
  const text = 'WWWW iiii WWWW iiii';
  const measure = (part: string) => Array.from(part).reduce((width, char) => width + (char === 'W' ? 4 : 1), 0);
  const pages = paginate(text, (part) => measure(part) <= 10);
  expect(pages.map((page) => page.text).join('')).toBe(text);
  expect(pages.every((page) => measure(page.text) <= 10)).toBe(true);
});

test('handles unbroken text and emoji without losing content or splitting surrogate pairs', () => {
  const text = '🌙'.repeat(13);
  const pages = paginate(text, (part) => Array.from(part).length <= 3);
  expect(pages).toHaveLength(5);
  expect(pages.map((page) => page.text).join('')).toBe(text);
  expect(pages.every((page) => !page.text.includes('\uFFFD'))).toBe(true);
});

test('retains the reading position when a viewport change repaginates text', () => {
  const text = 'abcdefghijklmnopqrstuvwxyz';
  const wide = paginate(text, (part) => part.length <= 10);
  const narrow = paginate(text, (part) => part.length <= 6);
  expect(pageAt(narrow, wide[1].start)).toBe(1);
  expect(narrow[pageAt(narrow, wide[1].start)].text).toContain('k');
  expect(pageAt(wide, 999)).toBe(2);
});

test('empty text and a zero-capacity viewport still terminate', () => {
  expect(paginate('', () => true)).toEqual([{ start: 0, end: 0, text: '' }]);
  expect(paginate('abc', () => false).map((page) => page.text)).toEqual(['a', 'b', 'c']);
});
