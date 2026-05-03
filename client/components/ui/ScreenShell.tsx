import React from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export function ScreenShell({ children }: { children: React.ReactNode }) {
  return (
    <SafeAreaView className="flex-1 bg-canvas-default" edges={['top', 'bottom']}>
      <View className="flex-1">{children}</View>
    </SafeAreaView>
  );
}
