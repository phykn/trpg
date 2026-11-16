import { Pressable, Text } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Popover } from '@/components/ui/Popover';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';

// For now only a way back to the title, where a new game starts and this one can still be picked up.
export function SettingsMenu({ onNewGame, onClose }: { onNewGame: () => void; onClose: () => void }) {
  return (
    <Popover at="right-2 top-12 p-1.5" label={ko.settings} onClose={onClose}>
      <Pressable accessibilityRole="menuitem" onPress={onNewGame} style={pressed}
        className={control({ kind: 'row', tone: 'quiet' })}>
        <Icon name="retry" size={icon.md} color={colors.gold.fg} width={2} />
        <Text className={text({ kind: 'strong' })}>{ko.newGame}</Text>
      </Pressable>
    </Popover>
  );
}
