import React from 'react';
import { Keyboard, View } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

export function ScreenShell({ children }: { children: React.ReactNode }) {
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
        {children}
      </View>
    </SafeAreaView>
  );
}
