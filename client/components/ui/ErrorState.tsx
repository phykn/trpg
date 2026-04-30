import { Pressable, Text, View } from 'react-native';

import { CenterMessage } from './CenterMessage';

type Props = {
  message: string;
  onRetry: () => void;
};

export function ErrorState({ message, onRetry }: Props) {
  return (
    <CenterMessage>
      <View className="items-center gap-1">
        <Text
          className="font-sans-semibold text-meta text-danger-fg"
          style={{ letterSpacing: 1.2 }}
        >
          오류
        </Text>
        <Text className="font-sans text-body text-fg-default text-center">
          {message}
        </Text>
      </View>
      <Pressable
        onPress={onRetry}
        className="px-4 h-9 mt-2 rounded-md bg-canvas-inset border border-border-default items-center justify-center active:bg-border-default"
      >
        <Text className="font-sans-medium text-body text-fg-default">다시 시도</Text>
      </Pressable>
    </CenterMessage>
  );
}
