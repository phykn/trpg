import { Pressable, ScrollView, Text } from 'react-native';

import { pressed } from '@/components/ui/Button';
import { control, off, text, tone } from '@/design/ui';
import { ko } from '@/locale/ko';
import type { Act } from '@/services/types';

// The bets a typed action could lead to, offered right after it; each label says all it does.
export function OffersRow({ offers, locked, onAct }: { offers: Act[]; locked: boolean; onAct: (act: string) => void }) {
  if (!offers.length) return null;
  return (
    <ScrollView horizontal accessibilityLabel={ko.offers} showsHorizontalScrollIndicator={false}
      className="grow-0" contentContainerClassName="gap-2 px-3 pt-2">
      {offers.map((a) => (
        <Pressable key={a.id} accessibilityRole="button" accessibilityLabel={a.label} accessibilityState={{ disabled: locked }}
          disabled={locked} onPress={() => onAct(a.id)} style={pressed}
          className={`${control.pill} ${tone.offer} ${locked ? off : ''}`}>
          <Text className={text.label}>{a.label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}
