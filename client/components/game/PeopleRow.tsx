import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { findHue } from './speaker';

// What can be done here without words: looking around, and whom to talk to.
export function PeopleRow({ people, met, look, locked, onAct }: {
  people: GameView['people']; met: string[]; look: GameView['place']['look']; locked: boolean; onAct: (act: string) => void;
}) {
  if (!people.length && !look) return null;
  return (
    <View accessibilityLabel={ko.people} className="flex-row flex-wrap gap-2 px-3 pt-2">
      {look ? (
        <Pressable accessibilityRole="button" accessibilityLabel={ko.look} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(look.id)} style={pressed}
          className={`h-9 flex-row items-center justify-center gap-2 rounded-full border border-dashed border-border-strong px-4 ${locked ? 'opacity-60' : ''}`}>
          <Icon name="eye" size={16} color={colors.fg.muted} />
          <Text className="font-sans-semibold text-panel text-fg-muted">{ko.look}</Text>
        </Pressable>
      ) : null}
      {people.map(({ name, partner, act }) => (
        <Pressable key={name} accessibilityRole="button" accessibilityLabel={name}
          accessibilityState={{ selected: partner, disabled: locked || !act }} disabled={locked || !act}
          onPress={() => act && onAct(act)} style={pressed}
          className={`h-9 flex-row items-center justify-center gap-2 rounded-full border px-4 ${partner ? 'border-fg-default bg-fg-default' : 'border-border-strong'} ${locked ? 'opacity-60' : ''}`}>
          <View className={`h-2 w-2 rounded-full ${findHue(met, name).bg}`} />
          <Text className={`font-sans-semibold text-panel ${partner ? 'text-fg-on-emphasis' : 'text-fg-default'}`}>{name}</Text>
        </Pressable>
      ))}
    </View>
  );
}
