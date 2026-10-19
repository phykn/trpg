import { View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Choice, Shell } from './CardShell';

/** ui.md 5.3: one button per growth action, and later. */
export function GrowthCard({ growth, onPick, onLater }: { growth: GameView['growth']; onPick: (action: string) => void; onLater: () => void }) {
  return (
    <Shell title={ko.growthTitle} onClose={onLater}>
      <View className="flex-row flex-wrap gap-2">
        {growth.map((g) => <Choice key={g.action} label={g.label} onPress={() => onPick(g.action)} />)}
      </View>
      <View className="mt-auto"><Choice label={ko.later} onPress={onLater} /></View>
    </Shell>
  );
}
