import { Text } from 'react-native';

export function ActDivider({ text }: { text: string }) {
  return (
    <Text className="font-mono text-body text-fg-subtle italic text-center px-5">
      — {text} —
    </Text>
  );
}
