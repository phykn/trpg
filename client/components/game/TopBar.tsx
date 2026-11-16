import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

// Where you are, the time (red in the last turns), the notebook with what is unread, and settings.
export function TopBar({ view, onNotebook, onSettings }: { view: GameView; onNotebook: () => void; onSettings: () => void }) {
  const { last } = view.time;
  return (
    <View className={`min-h-12 flex-row items-center gap-1 border-b pl-3 pr-1 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <Icon name="place" size={icon.md} color={colors.gold.fg} width={2.2} />
      <Text accessibilityRole="header" numberOfLines={1} className={text({ kind: 'title' }, 'min-w-0 shrink font-serif')}>
        {view.place.name}
      </Text>
      <View className="min-w-0 flex-1" />
      <Icon name="clock" size={icon.sm} color={last ? colors.danger.fg : colors.fg.muted} width={2} />
      <Text numberOfLines={1} className={text({ kind: 'mono' }, 'shrink-0', last && 'text-danger-fg')}>{view.time.text}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel={view.badge ? `${ko.notebook} ${view.badge}` : ko.notebook}
        onPress={onNotebook} style={pressed}
        className={control({ kind: 'pill', tone: 'plain' }, 'h-10 gap-1 px-2')}>
        <Icon name="book" size={icon.lg} color={colors.fg.muted} width={2} />
        {/* What is unread matters, so its count stands as large as the icon beside it. */}
        {view.badge ? <Text className={text({ kind: 'title' }, 'font-mono-medium text-gold-fg')}>{view.badge}</Text> : null}
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={ko.settings} onPress={onSettings} style={pressed}
        className={control({ kind: 'icon', tone: 'plain' })}>
        <Icon name="settings" size={icon.lg} color={colors.fg.muted} width={2} />
      </Pressable>
    </View>
  );
}
