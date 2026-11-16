import { Text, View } from 'react-native';

import { text } from '@/design/ui';
import { ko } from '@/locale/ko';
import { Button } from './Button';

// When an answer never came, the one way on is to send the very same thing again.
export function Resend({ onResend }: { onResend: () => void }) {
  return (
    <View className="w-full flex-row items-center gap-3">
      <Text className={`min-w-0 flex-1 ${text.sub}`}>{ko.stuck}</Text>
      <Button icon="retry" label={ko.resend} onPress={onResend} />
    </View>
  );
}
