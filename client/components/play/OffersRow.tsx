import { Pressable, Text, View } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { colors, icon } from '@/design/tokens';
import { control, text } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Act, GameView } from '@/services/types';

// The dice a typed action could bet, then the next steps the player can take in one press.
export function OffersRow({ offers, suggest, locked, onAct, onSuggest }: {
  offers: Act[]; suggest: GameView['suggest']; locked: boolean; onAct: (act: string) => void;
  onSuggest: (suggestion: GameView['suggest'][number]) => void;
}) {
  if (!offers.length && !suggest.length) return null;
  return (
    <View accessibilityLabel={ko.offers} className="gap-2 px-3 pt-2">
      {offers.map((a) => (
        <Pressable key={a.id} accessibilityRole="button" accessibilityLabel={a.label} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(a.id)} style={pressed}
          className={control({ kind: 'pill', tone: 'offer', off: locked }, 'h-auto min-h-11 self-start py-1')}>
          <Icon name="dice" size={icon.md} color={colors.fg.default} width={2} />
          <Text className={text({ kind: 'label' })}>{a.label}</Text>
        </Pressable>
      ))}
      {suggest.length ? (
        <View className="flex-row gap-1.5">
          {suggest.map((s) => (
            <Pressable key={s.label} accessibilityRole="button" accessibilityState={{ disabled: locked }} disabled={locked}
              accessibilityLabel={s.cells ? ko.moveTo(s.label, s.cells) : s.label} onPress={() => onSuggest(s)} style={pressed}
              className={control({ kind: 'row', tone: 'quiet', off: locked }, 'min-h-11 min-w-0 flex-1 flex-col justify-center gap-0 px-1 py-1')}>
              <Text className={text({ kind: 'label' }, 'text-center')}>{s.label}</Text>
              {s.cells ? (
                <View className="flex-row items-center gap-1">
                  <Icon name="place" size={icon.sm} color={colors.fg.muted} />
                  <Text className={text({ kind: 'head' })}>{ko.cells(s.cells)}</Text>
                </View>
              ) : null}
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}
