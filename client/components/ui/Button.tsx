import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { colors } from '@/design/tokens';
import { Icon, type IconName } from './Icon';

// Every tappable part dims the same way while held.
export const pressed = ({ pressed: p }: { pressed: boolean }) => ({ opacity: p ? 0.7 : 1 });

// Primary is the one next step on a screen; secondary is any other choice.
export function Button({ label, sub, icon, tone = 'primary', disabled, onPress }: {
  label: string; sub?: string; icon?: IconName; tone?: 'primary' | 'secondary'; disabled?: boolean; onPress: () => void;
}) {
  const primary = tone === 'primary';
  const fg = primary ? colors.fg['on-emphasis'] : colors.fg.default;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={sub ? `${label}, ${sub}` : label}
      accessibilityState={{ disabled: !!disabled }} disabled={disabled} onPress={onPress} style={pressed}
      className={`h-12 flex-row items-center justify-center gap-2 rounded-full px-5 ${primary ? 'bg-gold-fg' : 'border border-border-strong'} ${disabled ? 'opacity-40' : ''}`}>
      {icon ? <Icon name={icon} size={16} color={fg} width={2} /> : null}
      <Text className="font-sans-semibold text-body" style={{ color: fg }}>{label}</Text>
      {sub ? <Text numberOfLines={1} className="min-w-0 shrink font-sans text-panel" style={{ color: fg, opacity: 0.7 }}>{sub}</Text> : null}
    </Pressable>
  );
}

export function IconButton({ icon, label, onPress, tone = 'plain', size = 36, open, dot, disabled, children }: {
  icon?: IconName; label: string; onPress?: () => void; tone?: 'plain' | 'gold' | 'outline'; size?: number;
  open?: boolean; dot?: boolean; disabled?: boolean; children?: ReactNode;
}) {
  const off = disabled || !onPress;
  const fg = tone === 'gold' ? colors.fg['on-emphasis'] : open ? colors.gold.fg : colors.fg.muted;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: off, expanded: open }}
      disabled={off} onPress={onPress} style={pressed}
      className={`flex-row items-center justify-center gap-1.5 rounded-full ${tone === 'gold' ? 'bg-gold-fg' : ''} ${tone === 'outline' ? 'border border-border-default' : ''} ${open ? 'bg-gold-muted' : ''} ${off ? 'opacity-40' : ''}`}>
      <View style={{ minWidth: size, height: size }} className="flex-row items-center justify-center gap-1.5 px-1">
        {children}
        {icon ? <Icon name={icon} size={Math.round(size * 0.5)} color={fg} width={2} /> : null}
      </View>
      {dot ? <View className="absolute right-1 top-1 h-2 w-2 rounded-full bg-gold-fg" /> : null}
    </Pressable>
  );
}
