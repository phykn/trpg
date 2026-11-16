import '../global.css';

import { GeistMono_500Medium } from '@expo-google-fonts/geist-mono';
import { NanumGothic_400Regular, NanumGothic_700Bold } from '@expo-google-fonts/nanum-gothic';
import { NanumMyeongjo_400Regular, NanumMyeongjo_800ExtraBold } from '@expo-google-fonts/nanum-myeongjo';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';

import { colors } from '@/design/tokens';

export default function RootLayout() {
  const [loaded, error] = useFonts({
    NanumGothic_400Regular, NanumGothic_700Bold, NanumMyeongjo_400Regular, NanumMyeongjo_800ExtraBold, GeistMono_500Medium,
  });
  // A font that fails to load falls back to the system font rather than leaving the screen blank.
  if (!loaded && !error) return null;
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas.default } }} />;
}
