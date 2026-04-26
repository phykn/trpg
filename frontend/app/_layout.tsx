import '../global.css';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';

import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  useFonts as useInter,
} from '@expo-google-fonts/inter';
import {
  SourceSerif4_400Regular,
  SourceSerif4_500Medium,
  useFonts as useSerif,
} from '@expo-google-fonts/source-serif-4';
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
  const [interLoaded] = useInter({ Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold });
  const [serifLoaded] = useSerif({ SourceSerif4_400Regular, SourceSerif4_500Medium });
  const [monoLoaded]  = useMono({ GeistMono_400Regular, GeistMono_500Medium, GeistMono_600SemiBold });

  if (!interLoaded || !serifLoaded || !monoLoaded) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}
