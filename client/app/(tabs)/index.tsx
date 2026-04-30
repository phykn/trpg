import React from 'react';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Keyboard, View } from 'react-native';
import { PaperGrain } from '@/components/PaperGrain';
import { Shell } from '@/components/Shell';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [kb, setKb] = React.useState(0);

  React.useEffect(() => {
    const show = Keyboard.addListener('keyboardDidShow', (e) => setKb(e.endCoordinates.height));
    const hide = Keyboard.addListener('keyboardDidHide', () => setKb(0));
    return () => {
      show.remove();
      hide.remove();
    };
  }, []);

  return (
    <SafeAreaView
      className="flex-1 bg-canvas-default"
      edges={kb > 0 ? ['top'] : ['top', 'bottom']}
    >
      <View className="flex-1" style={{ paddingBottom: kb > 0 ? kb + insets.bottom : 0 }}>
        <Shell />
        <PaperGrain />
      </View>
    </SafeAreaView>
  );
}
