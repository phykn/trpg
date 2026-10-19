import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

// Every row names its category so the screen reads without help text (ui.md 2.1).
// Wrap, never truncate: names are never shortened.
export function Row({ label, children, inset }: { label: ReactNode; children: ReactNode; inset?: boolean }) {
  return (
    <View className={`flex-row items-start py-0.5 ${inset ? 'pl-4 pr-3' : 'px-4'}`}>
      {typeof label === 'string'
        ? <Text className="w-[52px] font-sans text-chip text-fg-subtle">{label}</Text>
        : <View className="min-w-[52px]">{label}</View>}
      <View className="min-w-0 flex-1 flex-row flex-wrap items-center" style={{ columnGap: 10, rowGap: 2 }}>
        {children}
      </View>
    </View>
  );
}

// Break Korean lines between words, so a sentence never leaves one syllable on its own line.
export const keepWords = { wordBreak: 'keep-all' } as object;

export function Item({ children, dim, tone, color: hue }: {
  children: ReactNode; dim?: boolean; tone?: 'danger' | 'gold' | 'muted'; color?: string;
}) {
  const color = tone === 'danger' ? 'text-danger-fg' : tone === 'gold' ? 'text-gold-fg' : tone === 'muted' ? 'text-fg-muted' : 'text-fg-default';
  return <Text className={`font-sans text-chip ${color}`} style={[{ opacity: dim ? 0.45 : 1, color: hue }, keepWords]}>{children}</Text>;
}
