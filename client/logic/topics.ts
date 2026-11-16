// Cuts what a person says into plain runs and the topic names in it, longest name first where two overlap.
export function splitTopics(text: string, topics: string[] = []): { text: string; topic: boolean }[] {
  const names = [...topics].filter(Boolean).sort((a, b) => b.length - a.length);
  if (!names.length) return text ? [{ text, topic: false }] : [];
  const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return text.split(new RegExp(`(${names.map(escape).join('|')})`)).filter(Boolean)
    .map((part) => ({ text: part, topic: names.includes(part) }));
}
