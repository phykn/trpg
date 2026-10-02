import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function BattleStatus({ battle }: { battle: NonNullable<GameView['combat']> }) {
  const hearts = (count: number) => '♥'.repeat(count) + '♡'.repeat(3 - count);
  return (
    <View className="gap-2 border-b border-border-default pb-4">
      <View className="flex-row items-center justify-between gap-3">
        <Text accessibilityLabel={`${ko.you} ${ko.hearts} ${battle.player_hearts}/3`} className="font-mono text-title text-hp-fg">{hearts(battle.player_hearts)}</Text>
        <Text className="flex-1 text-center font-sans-semibold text-body text-fg-default">{battle.opponent}</Text>
        <Text accessibilityLabel={`${battle.opponent} ${ko.hearts} ${battle.enemy_hearts}/3`} className="font-mono text-title text-gold-fg">{hearts(battle.enemy_hearts)}</Text>
      </View>
      <Text className="text-center font-sans text-caption text-success-fg">{ko.understanding[Math.min(battle.understanding, 2)]}</Text>
    </View>
  );
}
