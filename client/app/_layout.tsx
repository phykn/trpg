import '../global.css';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';

import {
  NotoSerifKR_400Regular,
  NotoSerifKR_500Medium,
  NotoSerifKR_600SemiBold,
  NotoSerifKR_700Bold,
  useFonts as useSerif,
} from '@expo-google-fonts/noto-serif-kr';
import {
  GeistMono_400Regular,
  GeistMono_500Medium,
  GeistMono_600SemiBold,
  useFonts as useMono,
} from '@expo-google-fonts/geist-mono';

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const [serifLoaded] = useSerif({
    NotoSerifKR_400Regular,
    NotoSerifKR_500Medium,
    NotoSerifKR_600SemiBold,
    NotoSerifKR_700Bold,
  });
  const [monoLoaded] = useMono({ GeistMono_400Regular, GeistMono_500Medium, GeistMono_600SemiBold });

  if (!serifLoaded || !monoLoaded) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
