import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

export function Shell({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <View className="flex-1 gap-3 rounded-t-xl border border-border-strong bg-canvas-floating px-4 pb-4 pt-4">
      {title ? <Text accessibilityRole="header" className="font-sans-semibold text-title text-fg-default">{title}</Text> : null}
      {children}
    </View>
  );
}

export function Choice({ label, sub, onPress, primary }: { label: string; sub?: string; onPress: () => void; primary?: boolean }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      className={`rounded-md border px-3 py-2 ${primary ? 'border-gold-fg bg-accent-muted' : 'border-border-default'}`}>
      <Text className={`font-sans-semibold text-body ${primary ? 'text-gold-fg' : 'text-fg-default'}`}>{label}</Text>
      {sub ? <Text className="font-sans text-panel text-fg-muted">{sub}</Text> : null}
    </Pressable>
  );
}
