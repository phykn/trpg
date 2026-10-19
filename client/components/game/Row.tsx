import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

// Every row names its category so the screen reads without help text (ui.md 2.1).
// Wrap, never truncate: names are never shortened.
export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <View className="flex-row items-start px-4 py-0.5">
      <Text className="w-[40px] pt-[1px] font-sans text-chip text-fg-subtle">{label}</Text>
      <View className="min-w-0 flex-1 flex-row flex-wrap items-center" style={{ columnGap: 10, rowGap: 2 }}>
        {children}
      </View>
    </View>
  );
}

export function Group({ children }: { children: ReactNode }) {
  return <View className="border-t border-border-default py-1">{children}</View>;
}

export function Item({ children, dim, tone, color: hue }: {
  children: ReactNode; dim?: boolean; tone?: 'danger' | 'gold' | 'muted'; color?: string;
}) {
  const color = tone === 'danger' ? 'text-danger-fg' : tone === 'gold' ? 'text-gold-fg' : tone === 'muted' ? 'text-fg-muted' : 'text-fg-default';
  return <Text className={`font-sans text-chip ${color}`} style={{ opacity: dim ? 0.45 : 1, color: hue }}>{children}</Text>;
}
