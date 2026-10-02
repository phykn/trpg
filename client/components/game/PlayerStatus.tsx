import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Button } from '@/components/ui/Button';

export function PlayerStatus({ view, onMenu }: { view: GameView; onMenu: () => void }) {
  return (
    <View className="gap-3 border-b border-border-default px-6 py-4">
      <View className="flex-row items-center justify-between gap-3">
        <View className="flex-1 min-w-0 gap-1">
          <Text className={`font-sans text-caption ${view.remaining <= 6 ? 'text-hp-fg' : 'text-gold-fg'}`}>{view.clock}</Text>
          <Text accessibilityRole="header" className="font-sans-semibold text-scene text-fg-default">{view.scene.name}</Text>
        </View>
        <Button label={ko.menu} onPress={onMenu} />
      </View>
      <View className="flex-row flex-wrap gap-x-4 gap-y-1">
        <Text className="font-sans text-caption text-fg-muted">{ko.hp} <Text className="font-mono text-hp-fg">{view.hp}/{view.max_hp}</Text></Text>
        <Text className="font-sans text-caption text-fg-muted">{ko.mp} <Text className="font-mono text-mp-fg">{view.mp}/{view.max_mp}</Text></Text>
        <Text className="font-sans text-caption text-fg-muted">{ko.gold} <Text className="font-mono text-gold-fg">{view.gold}</Text></Text>
      </View>
    </View>
  );
}
