import '../global.css';
import 'react-native-reanimated';

import { GeistMono_500Medium } from '@expo-google-fonts/geist-mono';
import { NanumGothic_400Regular, NanumGothic_700Bold } from '@expo-google-fonts/nanum-gothic';
import { NanumMyeongjo_400Regular, NanumMyeongjo_800ExtraBold } from '@expo-google-fonts/nanum-myeongjo';
import { DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';

import { colors } from '@/design/tokens';

export default function RootLayout() {
  const [loaded, error] = useFonts({
    NanumGothic_400Regular, NanumGothic_700Bold, NanumMyeongjo_400Regular, NanumMyeongjo_800ExtraBold,
    GeistMono_500Medium,
  });
  if (!loaded && !error) return null;

  return (
    <ThemeProvider value={DefaultTheme}>
      <View className="flex-1 bg-canvas-default">
        <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.canvas.default } }} />
      </View>
      <StatusBar style="dark" />
    </ThemeProvider>
  );
}
