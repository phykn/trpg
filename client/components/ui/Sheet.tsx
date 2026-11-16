import { Pressable, Text, View } from 'react-native';

import { colors, icon as iconSize } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import { IconButton, pressed } from './Button';
import { Icon } from './Icon';

// The title and the close button, the same on every sheet.
export function SheetHeader({ title, onClose }: { title?: string; onClose?: () => void }) {
  return (
    <View className="min-h-9 flex-row items-center gap-2">
      {title ? (
        <Text accessibilityRole="header" className={text({ kind: 'title' }, 'min-w-0 flex-1')}>{title}</Text>
      ) : <View className="flex-1" />}
      {onClose ? <IconButton icon="close" label={ko.close} onPress={onClose} /> : null}
    </View>
  );
}

// One row per answer: the same height, the same left edge, a chevron that says it goes on.
export function Choice({ label, sub, primary, onPress }: {
  label: string; sub?: string; primary?: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={sub ? `${label}, ${sub}` : label} onPress={onPress}
      style={pressed}
      className={control({ kind: 'row', tone: primary ? 'picked' : 'quiet' })}>
      <View className="min-w-0 flex-1">
        <Text className={text({ kind: 'strong', on: primary })}>{label}</Text>
        {sub ? <Text className={text({ kind: 'sub', on: primary })}>{sub}</Text> : null}
      </View>
      <Icon name="next" size={iconSize.sm} color={primary ? colors.fg['on-emphasis'] : colors.fg.subtle} />
    </Pressable>
  );
}
