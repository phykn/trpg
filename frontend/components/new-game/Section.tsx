import React from 'react';
import { Text, View } from 'react-native';

export function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View className="gap-2.5">
      <Text
        className="font-sans-semibold text-panel text-fg-subtle"
        style={{ letterSpacing: 1.2 }}
      >
        {label}
      </Text>
      <View className="gap-2">{children}</View>
    </View>
  );
}
