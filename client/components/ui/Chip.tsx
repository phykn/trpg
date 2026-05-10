import React from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';

type ChipProps =
  | { variant: 'tab'; label: string; active: boolean; dot?: boolean; onPress: () => void }
  | { variant: 'action'; label: string; onPress: () => void };

export function Chip(props: ChipProps) {
  if (props.variant === 'tab') return <TabChip {...props} />;
  return <ActionChip {...props} />;
}

function TabChip({ label, active, dot, onPress }: {
  label: string;
  active: boolean;
  dot?: boolean;
  onPress: () => void;
}) {
  const bg = active ? 'bg-accent-muted border-accent-fg' : 'bg-canvas-inset border-border-default active:bg-canvas-subtle';
  const fontWeight = active ? 'font-sans-semibold' : 'font-sans-medium';
  const color = active ? 'text-fg-default' : 'text-fg-muted';
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      className={`flex-1 min-w-0 h-8 px-2 flex-row items-center justify-center gap-1.5 rounded-full border ${bg}`}
    >
      <Text numberOfLines={1} className={`text-caption ${fontWeight} ${color}`}>
        {label}
      </Text>
      {dot && (
        <View
          style={{
            position: 'absolute',
            top: 6,
            right: 6,
            width: 6,
            height: 6,
            borderRadius: 3,
            backgroundColor: colors.accent.fg,
          }}
        />
      )}
    </Pressable>
  );
}

function ActionChip({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      className="h-5 shrink-0 items-center justify-center rounded-sm border border-accent-fg bg-accent-muted px-2 active:opacity-80"
    >
      <Text numberOfLines={1} className="font-sans-semibold text-caption text-accent-fg">{label}</Text>
    </Pressable>
  );
}
