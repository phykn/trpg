export type TextPage = { start: number; end: number; text: string };

export function paginate(text: string, fits: (part: string) => boolean): TextPage[] {
  const chars = Array.from(text);
  const pages: TextPage[] = [];
  let start = 0;
  let offset = 0;
  while (start < chars.length) {
    let low = start + 1;
    let high = chars.length;
    let end = low;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (fits(chars.slice(start, mid).join(''))) {
        end = mid;
        low = mid + 1;
      } else high = mid - 1;
    }
    if (end < chars.length) {
      // Prefer ending a page with a sentence, then with a word; never mid-word when a space fits.
      const earliest = start + Math.floor((end - start) * 0.5);
      const sentence = (i: number) => chars[i - 1] === '\n' || (/[.!?。！？"”']/u.test(chars[i - 1]) && /\s/u.test(chars[i] ?? ' '));
      const word = (i: number) => /\s/u.test(chars[i - 1]);
      for (const ok of [sentence, word]) {
        const found = Array.from({ length: end - earliest }, (_, k) => end - k).find(ok);
        if (found) { end = found; break; }
      }
    }
    const part = chars.slice(start, end).join('');
    pages.push({ start: offset, end: offset + part.length, text: part });
    offset += part.length;
    start = end;
  }
  return pages.length ? pages : [{ start: 0, end: 0, text: '' }];
}

export function pageAt(pages: TextPage[], offset: number): number {
  const index = pages.findIndex((page) => page.end > offset);
  return index < 0 ? pages.length - 1 : index;
}
