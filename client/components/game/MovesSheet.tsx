import { View } from 'react-native';

import { Choice, Sheet } from '@/components/ui/Sheet';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function MovesSheet({ moves, locked, onMove, onClose }: {
  moves: GameView['place']['moves']; locked: boolean; onMove: (act: string) => void; onClose: () => void;
}) {
  return (
    <Sheet title={ko.moves} icon="arrow" onClose={onClose}>
      <View className="gap-2">
        {moves.map((m) => (
          <Choice key={m.id} label={m.name} sub={[ko.cells(m.cells), m.unvisited ? ko.unvisited : null].filter(Boolean).join(' · ')}
            onPress={() => !locked && onMove(m.id)} />
        ))}
      </View>
    </Sheet>
  );
}
