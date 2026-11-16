import { Pressable, Text } from 'react-native';

import { colors, icon as iconSize } from '@/design/tokens';
import { cn, control, text } from '@/design/ui';
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
      className={control({ kind: 'button', tone: primary ? 'active' : 'idle', off: disabled })}>
      {icon ? <Icon name={icon} size={iconSize.md} color={fg} width={2} /> : null}
      <Text className={text({ kind: 'strong', on: primary })}>{label}</Text>
    </Pressable>
  );
}

export function IconButton({ icon, label, size = 36, disabled, onPress }: {
  icon: IconName; label: string; size?: number; disabled?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled }}
      disabled={disabled} onPress={onPress} style={(state) => ({ ...pressed(state), width: size, height: size })}
      className={cn('items-center justify-center rounded-full', disabled && 'opacity-40')}>
      <Icon name={icon} size={Math.round(size * 0.5)} color={colors.fg.muted} width={2} />
    </Pressable>
  );
}
