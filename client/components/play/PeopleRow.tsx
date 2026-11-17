import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon, type IconName } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { GameView } from '@/services/types';
import { findHue } from './speaker';

function Move({ label, name, locked, onPress }: { label: string; name: IconName; locked: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: locked }}
      disabled={locked} onPress={onPress} style={pressed} className={control({ kind: 'pill', off: locked })}>
      <Icon name={name} size={icon.md} color={colors.fg.default} width={2} />
      <Text className={text({ kind: 'label' })}>{label}</Text>
    </Pressable>
  );
}

export function PeopleRow({ people, met, look, locked, onAct, onMoves }: {
  people: GameView['people']; met: string[]; look: GameView['place']['look']; locked: boolean; onAct: (act: string) => void;
  onMoves?: () => void;
}) {
  if (!people.length && !look && !onMoves) return null;
  return (
    <View accessibilityLabel={ko.people} className="flex-row flex-wrap gap-2 px-3 pt-2">
      {look ? <Move label={ko.look} name="eye" locked={locked} onPress={() => onAct(look.id)} /> : null}
      {onMoves ? <Move label={ko.moves} name="place" locked={locked} onPress={onMoves} /> : null}
      {people.map(({ name, partner, act }) => (
        <Pressable key={name} accessibilityRole="button" accessibilityLabel={name}
          aria-pressed={partner} disabled={locked || !act}
          onPress={() => act && onAct(act)} style={pressed}
          className={control({ kind: 'pill', tone: partner ? 'active' : 'idle', off: locked })}>
          <View className={`h-2 w-2 rounded-full ${findHue(met, name).bg}`} />
          <Text className={text({ kind: 'label', on: partner })}>{name}</Text>
        </Pressable>
      ))}
    </View>
  );
}
