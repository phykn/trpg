import { View, Text } from 'react-native';

export function PlayerMessage({ text }: { text: string }) {
  return (
    <View
      className="self-end py-2.5 px-3.5 bg-accent-muted rounded-md"
      style={{ maxWidth: '82%', borderBottomRightRadius: 6 }}
    >
      <Text className="font-mono-medium text-title text-accent-fg">{text}</Text>
    </View>
  );
}
