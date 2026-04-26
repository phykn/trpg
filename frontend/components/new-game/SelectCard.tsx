import { Pressable, Text } from 'react-native';

type Props = {
  title: string;
  description?: string;
  selected: boolean;
  onPress: () => void;
};

export function SelectCard({ title, description, selected, onPress }: Props) {
  const bg = selected ? 'bg-accent-muted border-accent-fg' : 'bg-canvas-subtle border-border-default';
  return (
    <Pressable
      onPress={onPress}
      className={`px-4 py-3 rounded-md border ${bg}`}
      style={{ borderWidth: 1.5 }}
    >
      <Text
        className={`font-sans-semibold text-title ${
          selected ? 'text-accent-fg' : 'text-fg-default'
        }`}
      >
        {title}
      </Text>
      {description ? (
        <Text className="font-sans text-body text-fg-muted mt-1">{description}</Text>
      ) : null}
    </Pressable>
  );
}
