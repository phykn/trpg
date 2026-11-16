import { Pressable, Text } from 'react-native';

import { colors, icon as iconSize } from '@/design/tokens';
import { control, off, text, tone as tones } from '@/design/ui';
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
      className={`${control.button} ${primary ? tones.picked : tones.idle} ${disabled ? off : ''}`}>
      {icon ? <Icon name={icon} size={iconSize.md} color={fg} width={2} /> : null}
      <Text className={primary ? text.strongOn : text.strong}>{label}</Text>
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
      className={`items-center justify-center rounded-full ${gold ? 'bg-gold-fg' : ''} ${disabled ? off : ''}`}>
      <Icon name={icon} size={Math.round(size * 0.5)} color={gold ? colors.fg['on-emphasis'] : colors.fg.muted} width={2} />
    </Pressable>
  );
}
