import React from 'react';
import { View, Text } from 'react-native';
import { Theme, typeStyle } from '@/constants/theme';

export function LabeledRow({ label, children, mono = false, align = 'baseline' }: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
  align?: 'baseline' | 'center' | 'flex-start';
}) {
  const isText = typeof children === 'string' || typeof children === 'number';
  return (
    <View style={{
      flexDirection: 'row',
      gap: Theme.space.md,
      alignItems: align === 'baseline' ? 'flex-start' : align,
    }}>
      <Text style={{
        ...typeStyle('caption', { fontWeight: '600' as const, letterSpacing: 1.2 }),
        color: Theme.textFaint, flexShrink: 0, minWidth: 40, paddingTop: 2,
        textTransform: 'uppercase', fontFamily: Theme.fonts.monoSemibold,
      }}>{label}</Text>
      <View style={{ flex: 1, minWidth: 0 }}>
        {isText ? (
          <Text numberOfLines={1} style={{
            ...typeStyle('body'),
            color: Theme.text,
            fontFamily: mono ? Theme.fonts.monoRegular : Theme.fonts.sansRegular,
          }}>{children}</Text>
        ) : children}
      </View>
    </View>
  );
}
