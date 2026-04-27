import { Pressable, Text } from 'react-native';

import { colors } from '@/design/tokens';

type Props = {
  title: string;
  description?: string;
  selected: boolean;
  onPress: () => void;
};

export function SelectCard({ title, description, selected, onPress }: Props) {
  const bg = selected ? 'bg-accent-muted' : 'bg-canvas-subtle active:bg-canvas-inset';
  const borderClass = selected ? 'border-accent-fg' : 'border-border-default';
  return (
    <Pressable
      onPress={onPress}
      className={`px-4 py-3 rounded-md border ${borderClass} ${bg}`}
      style={selected ? { borderLeftWidth: 2, borderLeftColor: colors.accent.fg } : undefined}
    >
      <Text
        className={`font-serif-medium text-title ${
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
