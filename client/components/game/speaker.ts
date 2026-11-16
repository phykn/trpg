import { colors } from '@/design/tokens';

// Literal class names so Tailwind keeps them; a person's hue is their place among the people in the notebook.
const HUES = [
  { text: 'text-speaker-1', bg: 'bg-speaker-1', border: 'border-speaker-1', color: colors.speaker[1] },
  { text: 'text-speaker-2', bg: 'bg-speaker-2', border: 'border-speaker-2', color: colors.speaker[2] },
  { text: 'text-speaker-3', bg: 'bg-speaker-3', border: 'border-speaker-3', color: colors.speaker[3] },
  { text: 'text-speaker-4', bg: 'bg-speaker-4', border: 'border-speaker-4', color: colors.speaker[4] },
  { text: 'text-speaker-5', bg: 'bg-speaker-5', border: 'border-speaker-5', color: colors.speaker[5] },
  { text: 'text-speaker-6', bg: 'bg-speaker-6', border: 'border-speaker-6', color: colors.speaker[6] },
];
const UNMET = { text: 'text-fg-muted', bg: 'bg-border-strong', border: 'border-border-strong', color: colors.border.strong };

export function findHue(met: string[], name: string) {
  const i = met.indexOf(name);
  return i < 0 ? UNMET : HUES[i % HUES.length];
}
