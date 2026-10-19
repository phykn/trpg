import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

/** A wrapping row of chips: names are never shortened (ui.md 2.1). */
export function Row({ children, border = true }: { children: ReactNode; border?: boolean }) {
  return (
    <View className={`flex-row flex-wrap items-center px-4 py-1 ${border ? 'border-t border-border-default' : ''}`}
      style={{ columnGap: 10, rowGap: 2 }}>
      {children}
    </View>
  );
}

export function Item({ children, dim, tone }: { children: ReactNode; dim?: boolean; tone?: 'danger' | 'gold' | 'muted' }) {
  const color = tone === 'danger' ? 'text-danger-fg' : tone === 'gold' ? 'text-gold-fg' : tone === 'muted' ? 'text-fg-muted' : 'text-fg-default';
  return <Text className={`font-sans text-chip ${color}`} style={{ opacity: dim ? 0.45 : 1 }}>{children}</Text>;
}
