import { Pressable, Text, View } from 'react-native';

import type { GameView } from '@/services/types';

export function Buttons({ buttons, disabled, onPress }: {
  buttons: GameView['buttons']; disabled: boolean; onPress: (action: string) => void;
}) {
  return (
    <View className="gap-1 px-4">
      {buttons.slice(0, 3).map((b) => (
        <Pressable key={b.action} accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled}
          onPress={() => onPress(b.action)}
          className={`justify-center rounded-md border border-border-default px-3 ${disabled ? 'opacity-50' : 'active:opacity-80'}`}
          style={{ minHeight: 32 }}>
          <Text className="font-sans text-panel text-fg-default">{b.label}{b.rolls ? ' ⚄' : ''}</Text>
        </Pressable>
      ))}
    </View>
  );
}
