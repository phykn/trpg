import { Text, View } from 'react-native';

import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { Boxes } from './Boxes';

export function Meters({ view }: { view: GameView }) {
  if (!view.obstacles.length && !view.tags.length) return null;
  return (
    <View className="gap-2 border-b border-border-default px-6 py-3">
      {view.obstacles.map((o) => (
        <View key={o.id} className="flex-row items-center gap-2">
          <Text className="flex-1 font-sans text-panel text-fg-default">{o.name}{o.fits.length ? <Text className="text-fg-subtle"> · {o.fits.join(', ')}</Text> : null}</Text>
          <Boxes value={o.value} boxes={o.boxes} />
        </View>
      ))}
      {view.tags.length ? (
        <View className="flex-row flex-wrap gap-2">
          {view.tags.map((t) => (
            <Text key={t.id} className={`rounded-sm border px-2 py-0.5 font-sans text-caption ${t.kind === 'edge' ? 'border-success-fg text-success-fg' : 'border-danger-fg text-danger-fg'}`}>
              {t.kind === 'edge' ? ko.edge : ko.snag} · {t.name}{t.target ? ` → ${t.target}` : ''}
            </Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}
