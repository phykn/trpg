import React from 'react';
import { View } from 'react-native';

export function CenterMessage({ children }: { children: React.ReactNode }) {
  return (
    <View className="flex-1 bg-canvas-default items-center justify-center px-5 gap-2">
      {children}
    </View>
  );
}
