import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

// An icon and its words sit close; the groups stand apart, so the bar reads as a few things, not a run of glyphs.
function Item({ name, color, children }: { name: IconName; color: string; children: ReactNode }) {
  return (
    <View className="shrink-0 flex-row items-center gap-1">
      <Icon name={name} size={icon.md} color={color} width={2} />
      {children}
    </View>
  );
}

// Where you are, the time and the turns left (red in the last turns), the notebook with what is unread, and settings.
export function TopBar({ view, onNotebook, onSettings }: { view: GameView; onNotebook: () => void; onSettings: () => void }) {
  const { last } = view.time;
  const tone = last ? colors.danger.fg : colors.fg.muted;
  return (
    <View className={`min-h-12 flex-row items-center gap-2 border-b pl-3 pr-0.5 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <View className="min-w-0 flex-1 flex-row items-center gap-1.5">
        <Icon name="place" size={icon.md} color={colors.gold.fg} width={2.2} />
        <Text accessibilityRole="header" numberOfLines={1} className={text({ kind: 'title' }, 'min-w-0 shrink font-serif')}>
          {view.place.name}
        </Text>
      </View>
      {view.time.clock ? (
        <Item name="clock" color={tone}>
          <Text numberOfLines={1} className={text({ kind: 'bar' }, last && 'text-danger-fg')}>{view.time.clock}</Text>
        </Item>
      ) : null}
      <Item name="turns" color={tone}>
        <Text accessibilityLabel={ko.cells(view.time.left)} className={text({ kind: 'bar' }, last && 'text-danger-fg')}>
          {view.time.left}
        </Text>
      </Item>
      <Pressable accessibilityRole="button" accessibilityLabel={view.badge ? `${ko.notebook} ${view.badge}` : ko.notebook}
        onPress={onNotebook} style={pressed} className={control({ kind: 'icon', tone: 'plain' }, 'w-auto px-1.5')}>
        <Item name="book" color={colors.fg.muted}>
          {view.badge ? <Text className={text({ kind: 'bar' }, 'text-gold-fg')}>{view.badge}</Text> : null}
        </Item>
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={ko.settings} onPress={onSettings} style={pressed}
        className={control({ kind: 'icon', tone: 'plain' })}>
        <Icon name="settings" size={icon.md} color={colors.fg.muted} width={2} />
      </Pressable>
    </View>
  );
}
