import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

// The place opens where to go, the clock turns red in the last turns, and the notebook counts what is unread.
export function TopBar({ view, onPlace, onNotebook }: { view: GameView; onPlace?: () => void; onNotebook: () => void }) {
  const { last } = view.time;
  return (
    <View className={`min-h-12 flex-row items-center gap-2 border-b px-3 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <Pressable accessibilityRole="button" accessibilityLabel={`${view.place.name}, ${ko.moves}`}
        accessibilityState={{ disabled: !onPlace }} disabled={!onPlace} onPress={onPlace} style={pressed}
        className="min-w-0 flex-1 flex-row items-center gap-1">
        <Text accessibilityRole="header" numberOfLines={1} className={text({ kind: 'title' }, 'min-w-0 shrink')}>
          {view.place.name}
        </Text>
        {onPlace ? <Icon name="next" size={icon.sm} color={colors.fg.subtle} /> : null}
      </Pressable>
      <Text className={text({ kind: 'mono' }, last && 'text-danger-fg')}>{view.time.text}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel={view.badge ? `${ko.notebook} ${view.badge}` : ko.notebook}
        onPress={onNotebook} style={pressed}
        className={control({ kind: 'pill' }, 'pl-3', view.badge ? 'pr-1.5' : 'pr-3')}>
        <Icon name="book" size={icon.lg} color={colors.fg.muted} width={2} />
        <Text className={text({ kind: 'label' })}>{ko.notebook}</Text>
        {view.badge ? (
          <View className="h-6 min-w-6 items-center justify-center rounded-full bg-gold-muted px-1.5">
            <Text className="font-mono-medium text-chip text-gold-fg">{view.badge}</Text>
          </View>
        ) : null}
      </Pressable>
    </View>
  );
}
