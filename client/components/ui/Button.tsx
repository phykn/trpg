import { Pressable, Text } from 'react-native';

import { colors } from '@/design/tokens';
import { Icon, type IconName } from './Icon';

// Every tappable part dims the same way while held.
export const pressed = ({ pressed: p }: { pressed: boolean }) => ({ opacity: p ? 0.7 : 1 });

// Primary is the one next step on a screen; secondary is any other choice.
export function Button({ label, icon, tone = 'primary', disabled, onPress }: {
  label: string; icon?: IconName; tone?: 'primary' | 'secondary'; disabled?: boolean; onPress: () => void;
}) {
  const primary = tone === 'primary';
  const fg = primary ? colors.fg['on-emphasis'] : colors.fg.default;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }}
      disabled={disabled} onPress={onPress} style={pressed}
      className={`h-12 flex-row items-center justify-center gap-2 rounded-full px-5 ${primary ? 'bg-gold-fg' : 'border border-border-strong'} ${disabled ? 'opacity-40' : ''}`}>
      {icon ? <Icon name={icon} size={16} color={fg} width={2} /> : null}
      <Text className="font-sans-semibold text-body" style={{ color: fg }}>{label}</Text>
    </Pressable>
  );
}

export function IconButton({ icon, label, tone = 'plain', size = 36, disabled, onPress }: {
  icon: IconName; label: string; tone?: 'plain' | 'gold'; size?: number; disabled?: boolean; onPress: () => void;
}) {
  const gold = tone === 'gold';
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }}
      disabled={disabled} onPress={onPress} style={(state) => ({ ...pressed(state), width: size, height: size })}
      className={`items-center justify-center rounded-full ${gold ? 'bg-gold-fg' : ''} ${disabled ? 'opacity-40' : ''}`}>
      <Icon name={icon} size={Math.round(size * 0.5)} color={gold ? colors.fg['on-emphasis'] : colors.fg.muted} width={2} />
    </Pressable>
  );
}
