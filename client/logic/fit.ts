// Estimated without measuring: a Korean glyph is about one em wide, Latin about half.
export function linesAt(text: string, size: number, width: number): number {
  const perLine = width / size;
  let lines = 0;
  for (const paragraph of text.split('\n')) {
    let used = 0;
    let count = 1;
    for (const ch of paragraph) {
      const w = ch === ' ' ? 0.3 : /[\u0000-ÿ]/.test(ch) ? 0.55 : 1;
      if (used + w > perLine) { count += 1; used = w; } else used += w;
    }
    lines += count;
  }
  return lines;
}

export function fitSize(text: string, width: number, height: number, sizes: number[], lineHeight: number): number {
  for (const size of sizes) {
    if (linesAt(text, size, width) * size * lineHeight <= height) return size;
  }
  return sizes[sizes.length - 1];
}
