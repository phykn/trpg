import Head from 'expo-router/head';
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { ko } from '@/locale/ko';
import { useKeyboard } from '@/logic/useKeyboard';

// The same narrow phone frame on every screen width; the page around it never scrolls.
export function Frame({ title, children }: { title?: string; children: ReactNode }) {
  const { top, height } = useKeyboard();
  return (
    <View className="items-center bg-canvas-inset" style={{ height, transform: [{ translateY: top }] }}>
      <Head><title>{title ? `${title} · ${ko.brand}` : ko.brand}</title></Head>
      <View className="mobile-frame min-h-0 w-full max-w-mobile flex-1 border-x border-border-default bg-canvas-default">
        {children}
      </View>
    </View>
  );
}
