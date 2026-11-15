import Head from 'expo-router/head';
import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import { useViewportHeight } from '@/logic/useViewportHeight';

export default function Index() {
  const height = useViewportHeight();
  return (
    <View className="items-center bg-canvas-inset" style={{ height }}>
      <Head><title>{ko.brand}</title></Head>
      <View className="mobile-frame min-h-0 w-full max-w-mobile flex-1 items-center justify-center border-x border-border-default bg-canvas-default">
        <Text accessibilityRole="header" className="font-serif text-display tracking-[2px] text-fg-default">{ko.brand}</Text>
      </View>
    </View>
  );
}
