import { Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { Button } from './Button';
import { Icon } from './Icon';

export function Resend({ onResend }: { onResend: () => void }) {
  return (
    <View className="w-full flex-row items-center gap-3">
      <Text className="min-w-0 flex-1 font-sans text-panel text-fg-muted">{ko.stuck}</Text>
      <Button icon="retry" label={ko.resend} onPress={onResend} />
    </View>
  );
}

export function Notice({ text }: { text: string }) {
  return (
    <View accessibilityRole="alert" className="w-full flex-row items-center gap-1.5">
      <Icon name="alert" size={12} color={colors.danger.fg} />
      <Text className="min-w-0 flex-1 font-sans text-chip text-danger-fg">{text}</Text>
    </View>
  );
}
