import '../global.css';
import React from 'react';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform } from 'react-native';
import 'react-native-reanimated';

import {
  NanumGothic_400Regular,
  NanumGothic_700Bold,
  useFonts as useGothic,
} from '@expo-google-fonts/nanum-gothic';
import {
  GeistMono_400Regular,
  GeistMono_500Medium,
  GeistMono_600SemiBold,
  useFonts as useMono,
} from '@expo-google-fonts/geist-mono';

export const unstable_settings = {
  anchor: '(tabs)',
};

type NavigatorWithVirtualKeyboard = Navigator & {
  virtualKeyboard?: { overlaysContent: boolean };
};

function enableWebKeyboardOverlay() {
  if (Platform.OS !== 'web') return;

  const viewport = document.querySelector<HTMLMetaElement>('meta[name="viewport"]');
  if (viewport && !viewport.content.includes('interactive-widget=')) {
    viewport.content = `${viewport.content}, interactive-widget=overlays-content`;
  }

  const webNavigator = navigator as NavigatorWithVirtualKeyboard;
  if ('virtualKeyboard' in navigator && webNavigator.virtualKeyboard) {
    webNavigator.virtualKeyboard.overlaysContent = true;
  }
}

export default function RootLayout() {
  const [gothicLoaded] = useGothic({
    NanumGothic_400Regular,
    NanumGothic_700Bold,
  });
  const [monoLoaded] = useMono({ GeistMono_400Regular, GeistMono_500Medium, GeistMono_600SemiBold });

  React.useEffect(() => {
    enableWebKeyboardOverlay();
  }, []);

  if (!gothicLoaded || !monoLoaded) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
