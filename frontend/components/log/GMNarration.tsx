import { Text } from 'react-native';

export function GMNarration({ text }: { text: string }) {
  return (
    <Text className="font-serif text-lead text-fg-default">{text}</Text>
  );
}
