import { Pressable, ScrollView, Text } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Act, GameView } from '@/services/types';

// The dice a typed action could bet, then the next steps the player can take in one press.
export function OffersRow({ offers, suggest, locked, onAct, onSay }: {
  offers: Act[]; suggest: GameView['suggest']; locked: boolean; onAct: (act: string) => void; onSay: (text: string) => void;
}) {
  if (!offers.length && !suggest.length) return null;
  return (
    <ScrollView horizontal accessibilityLabel={ko.offers} showsHorizontalScrollIndicator={false}
      className="grow-0" contentContainerClassName="gap-2 px-3 pt-2">
      {offers.map((a) => (
        <Pressable key={a.id} accessibilityRole="button" accessibilityLabel={a.label} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(a.id)} style={pressed}
          className={control({ kind: 'pill', tone: 'offer', off: locked })}>
          <Icon name="dice" size={icon.md} color={colors.fg.default} width={2} />
          <Text className={text({ kind: 'label' })}>{a.label}</Text>
        </Pressable>
      ))}
      {suggest.map((s) => (
        <Pressable key={s.label} accessibilityRole="button" accessibilityState={{ disabled: locked }} disabled={locked}
          onPress={() => (s.id ? onAct(s.id) : onSay(s.text ?? s.label))} style={pressed}
          className={control({ kind: 'pill', tone: 'quiet', off: locked })}>
          <Text className={text({ kind: 'label' })}>{s.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
