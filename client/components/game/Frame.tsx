import Head from 'expo-router/head';
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { ko } from '@/locale/ko';
import { useViewportHeight } from '@/logic/useViewportHeight';

export function Frame({ title, children }: { title?: string; children: ReactNode }) {
  const height = useViewportHeight();
  return (
    <View className="items-center bg-canvas-inset" style={{ height }}>
      <Head><title>{title ? `${title} · ${ko.brand}` : ko.brand}</title></Head>
      <View className="mobile-frame min-h-0 w-full max-w-mobile flex-1 border-x border-border-default bg-canvas-default">
        {children}
      </View>
    </View>
  );
}
