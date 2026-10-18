import { Text, View } from 'react-native';

import { Button } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';

export function SceneHeader({ view, onSheet, onJournal }: { view: GameView; onSheet: () => void; onJournal: () => void }) {
  const danger = view.danger;
  const hot = danger.value >= danger.boxes - 2;
  return (
    <View className="gap-2 border-b border-border-default px-6 py-3">
      <View className="flex-row items-center gap-3">
        <View className="flex-1 min-w-0 gap-1">
          <Text className="font-sans text-caption text-gold-fg">{view.chapter}</Text>
          <Text accessibilityRole="header" className="font-sans-semibold text-title text-fg-default">{view.place.name}</Text>
        </View>
        <Button label={ko.sheet} onPress={onSheet} />
        <Button label={ko.journal} onPress={onJournal} />
      </View>
      <View className="flex-row items-center gap-2">
        <Text className={`flex-1 font-sans text-caption ${hot ? 'text-danger-fg' : 'text-fg-muted'}`}>{ko.danger} · {danger.name}</Text>
        <Boxes value={danger.value} boxes={danger.boxes} tone={hot ? 'danger' : 'muted'} />
      </View>
    </View>
  );
}
