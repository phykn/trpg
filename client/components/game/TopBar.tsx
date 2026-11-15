import { Pressable, Text, View } from 'react-native';

import { IconButton, pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function TopBar({ view, onPlace, onNotebook }: { view: GameView; onPlace?: () => void; onNotebook?: () => void }) {
  const last = view.time.last;
  return (
    <View className={`min-h-[48px] flex-row items-center gap-2 border-b px-3 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <Pressable accessibilityRole="button" accessibilityLabel={`${view.place.name}, ${ko.moves}`}
        accessibilityState={{ disabled: !onPlace }} disabled={!onPlace} onPress={onPlace} style={pressed}
        className="min-w-0 flex-1 flex-row items-center gap-1">
        <Text accessibilityRole="header" numberOfLines={1} className="min-w-0 shrink font-sans-semibold text-title text-fg-default">
          {view.place.name}
        </Text>
        {onPlace ? <Icon name="next" size={12} color={colors.fg.subtle} /> : null}
      </Pressable>
      <Text accessibilityLabel={view.time.text} className={`font-mono-medium text-panel ${last ? 'text-danger-fg' : 'text-fg-muted'}`}>
        {view.time.text}
      </Text>
      <IconButton icon="book" label={view.badge ? `${ko.notebook} ${view.badge}` : ko.notebook} onPress={onNotebook}
        tone="outline">
        {view.badge ? <Text className="font-mono-medium text-chip text-gold-fg">{view.badge}</Text> : null}
      </IconButton>
    </View>
  );
}
