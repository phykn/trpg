import type { ReactNode } from 'react';
import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

function Item({ name, color, children }: { name: IconName; color: string; children?: ReactNode }) {
  return (
    <View className="min-w-0 flex-row items-center gap-1">
      <Icon name={name} size={icon.md} color={color} width={2} />
      {children}
    </View>
  );
}

export function TopBar({ view, onNotebook, onSettings }: { view: GameView; onNotebook: () => void; onSettings: () => void }) {
  const { last } = view.time;
  const tone = last ? colors.danger.fg : colors.fg.muted;
  const word = () => text({ kind: 'bar' }, last && 'text-danger-fg');
  return (
    <View className={`min-h-12 flex-row items-center justify-between border-b px-3 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <View className="min-w-0 shrink">
        <Item name="place" color={colors.gold.fg}>
          <Text accessibilityRole="header" numberOfLines={1} className={text({ kind: 'bar' }, 'min-w-0 shrink text-fg-default')}>
            {view.place.name}
          </Text>
        </Item>
      </View>
      {view.time.clock ? (
        <Item name="clock" color={tone}><Text numberOfLines={1} className={word()}>{view.time.clock}</Text></Item>
      ) : null}
      <Item name="turns" color={tone}>
        <Text accessibilityLabel={ko.cells(view.time.left)} className={word()}>{view.time.left}</Text>
      </Item>
      <Pressable accessibilityRole="button" accessibilityLabel={view.badge ? `${ko.notebook} ${view.badge}` : ko.notebook}
        onPress={onNotebook} style={pressed} className={control({ kind: 'icon', tone: 'plain' }, 'w-auto')}>
        <Item name="book" color={colors.fg.muted}>
          {view.badge ? <Text className={text({ kind: 'bar' }, 'text-gold-fg')}>{view.badge}</Text> : null}
        </Item>
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={ko.settings} onPress={onSettings} style={pressed}
        className={control({ kind: 'icon', tone: 'plain' }, 'w-auto')}>
        <Item name="settings" color={colors.fg.muted} />
      </Pressable>
    </View>
  );
}
