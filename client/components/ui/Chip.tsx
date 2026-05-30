import React from 'react';
import { Pressable, Text, View } from 'react-native';

type ChipProps =
  | {
      variant: 'tab';
      label: string;
      active: boolean;
      onPress: () => void;
      dot?: boolean;
      dotAccessibilityLabel?: string;
    }
  | { variant: 'action'; label: string; onPress: () => void; disabled?: boolean };

export function Chip(props: ChipProps) {
  if (props.variant === 'tab') return <TabChip {...props} />;
  return <ActionChip {...props} />;
}

function TabChip({ label, active, onPress, dot = false, dotAccessibilityLabel }: {
  label: string;
  active: boolean;
  onPress: () => void;
  dot?: boolean;
  dotAccessibilityLabel?: string;
}) {
  const bg = active ? 'bg-accent-muted border-accent-fg' : 'bg-transparent border-border-default active:bg-canvas-subtle';
  const fontWeight = active ? 'font-sans-semibold' : 'font-sans-medium';
  const color = active ? 'text-fg-default' : 'text-fg-muted';
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      className={`flex-1 min-w-0 h-8 px-2 flex-row items-center justify-center gap-1.5 rounded-sm border ${bg}`}
    >
      <Text numberOfLines={1} className={`text-caption ${fontWeight} ${color}`}>
        {label}
      </Text>
      {dot ? (
        <View
          accessibilityLabel={dotAccessibilityLabel ?? label}
          className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-danger-fg"
        />
      ) : null}
    </Pressable>
  );
}

function ActionChip({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable
      onPress={disabled ? undefined : onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      className={`h-5 shrink-0 items-center justify-center rounded-sm border border-accent-fg bg-accent-muted px-2 ${disabled ? 'opacity-50' : 'active:opacity-80'}`}
    >
      <Text numberOfLines={1} className="font-sans-semibold text-caption text-accent-fg">{label}</Text>
    </Pressable>
  );
}
