import { Pressable, Text, View } from 'react-native';

import { speakerHue } from '@/components/game/speaker';
import { pressed } from '@/components/ui/Button';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';

export function PeopleRow({ people, met, locked, onFace }: {
  people: GameView['people']; met: string[]; locked: boolean; onFace: (act: string) => void;
}) {
  if (!people.length) return null;
  return (
    <View accessibilityLabel={ko.people} className="flex-row flex-wrap gap-2 px-3 pt-2">
      {people.map((p) => (
        <Pressable key={p.name} accessibilityRole="button" accessibilityLabel={p.name}
          accessibilityState={{ selected: p.partner, disabled: locked || !p.act }} disabled={locked || !p.act}
          onPress={() => p.act && onFace(p.act)} style={pressed}
          className={`h-9 flex-row items-center justify-center gap-2 rounded-full border px-4 ${p.partner ? 'border-fg-default bg-fg-default' : 'border-border-strong'} ${locked ? 'opacity-60' : ''}`}>
          <View className={`h-2 w-2 rounded-full ${speakerHue(met, p.name).bg}`} />
          <Text className={`font-sans-semibold text-panel ${p.partner ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{p.name}</Text>
        </Pressable>
      ))}
    </View>
  );
}
