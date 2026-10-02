import { Pressable, Text } from 'react-native';

type Props = {
  label: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
  selected?: boolean;
};

export function Button({ label, onPress, primary, disabled, selected }: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!disabled, selected }}
      disabled={disabled}
      onPress={onPress}
      className={`min-h-11 items-center justify-center rounded-md border px-4 py-2 ${
        primary ? 'border-gold-fg bg-gold-fg' : selected ? 'border-gold-fg bg-accent-muted' : 'border-border-default bg-transparent hover:bg-canvas-floating'
      } ${disabled ? 'opacity-50' : 'active:opacity-80'}`}
    >
      <Text className={`font-sans-semibold text-panel ${primary ? 'text-fg-on-emphasis' : selected ? 'text-gold-fg' : 'text-fg-default'}`}>{label}</Text>
    </Pressable>
  );
}
