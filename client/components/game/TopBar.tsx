import { Text, View } from 'react-native';

import { IconButton } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function TopBar({ view, onPlace, onNotebook }: { view: GameView; onPlace?: () => void; onNotebook?: () => void }) {
  const last = view.time.last;
  return (
    <View className={`min-h-[48px] flex-row items-center gap-2 border-b px-3 ${last ? 'border-danger-fg bg-canvas-subtle' : 'border-border-default'}`}>
      <Text accessibilityRole="header" numberOfLines={1} onPress={onPlace}
        className="min-w-0 flex-1 font-sans-semibold text-title text-fg-default">{view.place.name}</Text>
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
