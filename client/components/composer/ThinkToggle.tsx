import { Pressable, Text } from 'react-native';

export function ThinkToggle({ think, onToggle, disabled = false }: {
  think: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  const label = think ? '정확하게' : '빠르게';
  const bgClass = think ? 'bg-accent-muted' : 'bg-canvas-inset';
  const stateClass = disabled ? 'opacity-50' : 'active:opacity-80';
  return (
    <Pressable
      onPress={disabled ? undefined : onToggle}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected: think }}
      className={`items-center justify-center h-8 px-3 rounded-full ${stateClass} ${bgClass}`}
    >
      <Text className="font-sans text-panel text-fg-default">{label}</Text>
    </Pressable>
  );
}
