import React from 'react';
import { View, Text } from 'react-native';

type Props = {
  label: string;
  labelAlign?: 'left' | 'right';
  gap?: 'md' | 'lg';
  trailing?: React.ReactNode;
  children: React.ReactNode;
  variableHeight?: boolean;
};

const GAP_CLASS = {
  md: 'gap-3',
  lg: 'gap-4',
} as const;

export function Row({
  label,
  labelAlign = 'left',
  gap = 'md',
  trailing,
  children,
  variableHeight = false,
}: Props) {
  const heightClass = variableHeight ? 'min-h-5' : 'h-5';
  const alignClass = variableHeight ? 'items-start' : 'items-center';
  const labelAlignClass = labelAlign === 'right' ? 'text-right' : 'text-left';

  return (
    <View className={`flex-row ${GAP_CLASS[gap]} ${alignClass} ${heightClass} min-w-0`}>
      <Text
        className={`font-sans-semibold text-panel text-fg-subtle shrink-0 ${labelAlignClass}`}
        style={{ minWidth: 42, letterSpacing: 1.2 }}
      >
        {label}
      </Text>
      <View className="flex-1 min-w-0">{children}</View>
      {trailing}
    </View>
  );
}
