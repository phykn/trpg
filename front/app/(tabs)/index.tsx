import { SafeAreaView } from 'react-native-safe-area-context';
import { KeyboardAvoidingView, Platform } from 'react-native';
import { Shell } from '@/components/Shell';
import { Theme } from '@/constants/theme';

export default function HomeScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Theme.bg }} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <Shell />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
